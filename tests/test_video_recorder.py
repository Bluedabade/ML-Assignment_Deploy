"""Synthetic media only; no camera, SDK, or model weights."""
import base64
import io
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image
from skn_app.config import LIMITS
from skn_app.errors import AppError
from skn_app.media import process_video,csv_bytes,video_metadata,video_rotation
from skn_app.video_recorder import decode_clip
from skn_app.recording_media import normalize_recording


def synthetic(folder,format='mp4',seconds=1,size=(160,96)):
    import av
    path=Path(folder)/('synthetic.'+format)
    with av.open(str(path),'w',format=format) as c:
        stream=c.add_stream('libx264' if format=='mp4' else 'libvpx',rate=15)
        stream.width,stream.height=size;stream.pix_fmt='yuv420p';stream.thread_count=1
        for _ in range(seconds*15):
            for p in stream.encode(av.VideoFrame.from_image(Image.new('RGB',size,'#607080'))):c.mux(p)
        for p in stream.encode():c.mux(p)
    return path.read_bytes()


def oriented_video(folder,angle,*,flip=False,size=(160,96),seconds=1,fps=15):
    """Real MP4 display matrix on an asymmetric synthetic test card."""
    import av
    path=Path(folder)/'orientation.mp4'
    card=Image.new('RGB',size,'#20a040')
    card.paste('#d02030',(0,0,size[0]//2,size[1]//2))
    card.paste('#3040d0',(size[0]//2,0,size[0],size[1]//2))
    card.paste('#d0b020',(0,size[1]//2,size[0]//2,size[1]))
    with av.open(str(path),'w') as c:
        stream=c.add_stream('libx264',rate=fps);stream.width,stream.height=size
        stream.pix_fmt='yuv420p';stream.thread_count=1;stream.set_display_rotation(angle,hflip=flip)
        for _ in range(seconds*fps):
            for packet in stream.encode(av.VideoFrame.from_image(card)):c.mux(packet)
        for packet in stream.encode():c.mux(packet)
    return path.read_bytes()


class RecordingTests(unittest.TestCase):
    def test_uploaded_quarter_turns_reach_model_upright_and_keep_one_fps(self):
        import av
        class Runtime:
            def __init__(self):self.images=[];self.loads=0
            def load(self):self.loads+=1
            def predict(self,image,profile):
                self.images.append(image.copy())
                return [dict(class_name='enlarged_pore',confidence=.35,x1=10,y1=30,x2=40,y2=60)],.01
        for angle,operation in [(0,None),(90,Image.Transpose.ROTATE_90),(180,Image.Transpose.ROTATE_180),(270,Image.Transpose.ROTATE_270),(-90,Image.Transpose.ROTATE_270)]:
            with self.subTest(angle=angle),tempfile.TemporaryDirectory() as t,patch('skn_app.media.guard_memory'):
                data=oriented_video(t,angle,seconds=2)
                with av.open(io.BytesIO(data)) as c:expected=next(c.decode(video=0)).to_image().convert('RGB')
                if operation is not None:expected=expected.transpose(operation)
                runtime=Runtime();result=process_video(data,runtime,'Balanced',t)
                self.assertEqual(runtime.loads,1);self.assertEqual(len(runtime.images),2)
                self.assertEqual(runtime.images[0].tobytes(),expected.tobytes())
                self.assertEqual(result['counts']['enlarged_pore'],2)
                self.assertEqual(result['sampled_fps'],1)
                self.assertEqual([f['timestamp_seconds'] for f in result['frames']],[0.,1.])
                self.assertEqual((result['metadata']['width'],result['metadata']['height']),expected.size)
                self.assertEqual(result['predictions'][0]['x1'],10)
                self.assertEqual(result['csv_bytes'].splitlines()[0],csv_bytes([]).splitlines()[0])
                with av.open(io.BytesIO(result['video_bytes'])) as c:
                    output=list(c.decode(video=0))
                    self.assertEqual(c.streams.video[0].codec_context.name,'h264')
                    self.assertEqual(len(output),2);self.assertEqual((output[0].width,output[0].height),expected.size)
                    self.assertEqual(video_rotation(output[0]),0)

    def test_recorded_rotated_mp4_is_normalized_once_without_metadata_rotation(self):
        import av
        import numpy as np
        for angle,operation in [(90,Image.Transpose.ROTATE_90),(180,Image.Transpose.ROTATE_180),(270,Image.Transpose.ROTATE_270)]:
            with self.subTest(angle=angle),tempfile.TemporaryDirectory() as t,patch('skn_app.recording_media.guard_memory'),patch('skn_app.media.guard_memory'):
                data=oriented_video(t,angle)
                with av.open(io.BytesIO(data)) as c:expected=next(c.decode(video=0)).to_image().convert('RGB').transpose(operation)
                normalized=normalize_recording(data,t)
                self.assertNotEqual(normalized,data)
                with av.open(io.BytesIO(normalized)) as c:
                    frames=list(c.decode(video=0));self.assertEqual(len(frames),15)
                    self.assertEqual(video_rotation(frames[0]),0)
                    actual=frames[0].to_image().convert('RGB');self.assertEqual(actual.size,expected.size)
                    self.assertLess(np.abs(np.asarray(actual,dtype=float)-np.asarray(expected,dtype=float)).mean(),8)
                self.assertEqual(normalize_recording(normalized,t),normalized)

    def test_unsupported_matrix_rejected_before_model(self):
        runtime=SimpleNamespace(load=unittest.mock.Mock())
        for angle,flip in [(45,False),(0,True),(90,True)]:
            with self.subTest(angle=angle,flip=flip),tempfile.TemporaryDirectory() as t,patch('skn_app.media.guard_memory'),patch('skn_app.recording_media.guard_memory'):
                data=oriented_video(t,angle,flip=flip)
                for action in [lambda:process_video(data,runtime,'Balanced',t),lambda:normalize_recording(data,t)]:
                    with self.assertRaises(AppError) as error:action()
                    self.assertEqual(error.exception.code,'VIDEO_ROTATION')
                runtime.load.assert_not_called()

    def test_rotated_video_keeps_size_and_duration_guards(self):
        runtime=SimpleNamespace(load=unittest.mock.Mock())
        for args in [dict(size=(1282,720)),dict(seconds=13)]:
            with tempfile.TemporaryDirectory() as t,patch('skn_app.media.guard_memory'),patch('skn_app.recording_media.guard_memory'):
                data=oriented_video(t,90,**args)
                for action in [lambda:process_video(data,runtime,'Balanced',t),lambda:normalize_recording(data,t)]:
                    with self.assertRaises(AppError) as error:action()
                    self.assertEqual(error.exception.code,'VIDEO_LIMITS')
                runtime.load.assert_not_called()

    def test_legacy_rotation_tags_and_missing_frame_matrix(self):
        frame=SimpleNamespace(side_data=[])
        self.assertEqual(video_rotation(frame,{'rotate':'90'}),270)
        self.assertEqual(video_rotation(frame,{'rotate':'-90'}),90)
        self.assertEqual(video_rotation(frame,fallback=180),180)
        for tag in ('nan','45','broken'):
            with self.assertRaises(AppError):video_rotation(frame,{'rotate':tag})

    def test_rotated_recording_at_duration_limit_preserves_30fps_timestamps(self):
        import av
        with tempfile.TemporaryDirectory() as t,patch('skn_app.media.guard_memory'),patch('skn_app.recording_media.guard_memory'):
            data=oriented_video(t,90,seconds=12,fps=30)
            output=normalize_recording(data,t)
            with av.open(io.BytesIO(output)) as c:
                frames=list(c.decode(video=0));self.assertEqual(len(frames),360)
                self.assertAlmostEqual(float(frames[-1].time),359/30,places=4)
                self.assertLessEqual(c.duration/av.time_base,12.01)

    def test_transport_empty(self):self.assertIsNone(decode_clip(None))
    def test_transport_valid_mp4(self):
        with tempfile.TemporaryDirectory() as t:
            data=synthetic(t)
            self.assertEqual(decode_clip(dict(b64=base64.b64encode(data).decode(),mime='video/mp4',seconds=1)),(data,'video/mp4'))
    def test_transport_rejects_unsupported_mime_duration_and_corrupt_base64(self):
        good=dict(b64='YWJj',mime='video/mp4',seconds=1)
        for value in [dict(good,mime='image/png'),dict(good,seconds=13),dict(good,seconds=float('nan')),dict(good,b64='@@'),good,{},'video']:
            with self.assertRaises(AppError):decode_clip(value)
    def test_transport_rejects_size_before_decode(self):
        with self.assertRaises(AppError):decode_clip(dict(b64='A'*(4*((LIMITS.video_bytes+2)//3)+4),mime='video/mp4',seconds=1))
    def test_mp4_unchanged_and_input_folder_cleanup(self):
        with tempfile.TemporaryDirectory() as t,patch('skn_app.recording_media.guard_memory'):
            data=synthetic(t);self.assertEqual(normalize_recording(data,t),data)
        self.assertFalse(Path(t).exists())
    def test_webm_real_conversion_and_shared_sampled_pipeline(self):
        import av
        class Runtime:
            calls=0
            def load(self):pass
            def predict(self,image,profile):self.calls+=1;return [],.01
        with tempfile.TemporaryDirectory() as t,patch('skn_app.recording_media.guard_memory'),patch('skn_app.media.guard_memory'):
            data=synthetic(t,'webm',2);normalized=normalize_recording(data,t)
            self.assertEqual(normalized[4:8],b'ftyp');runtime=Runtime()
            result=process_video(normalized,runtime,'Balanced',t)
            self.assertEqual(runtime.calls,2);self.assertEqual(result['sampled_fps'],1)
            self.assertEqual(result['csv_bytes'].splitlines()[0],csv_bytes([]).splitlines()[0])
            with av.open(io.BytesIO(result['video_bytes'])) as c:self.assertEqual(c.streams.video[0].codec_context.name,'h264')
    def test_corrupted_video_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            for data in (b'bad',b'\x1aE\xdf\xa3broken',b'0000ftypbroken'):
                with self.assertRaises(AppError):normalize_recording(data,t)
    def test_duration_and_resolution_rejected_before_model(self):
        with tempfile.TemporaryDirectory() as t,patch('skn_app.recording_media.guard_memory'):
            for args in [dict(seconds=13),dict(size=(1282,720))]:
                with self.assertRaises(AppError):normalize_recording(synthetic(t,**args),t)
    def test_oversized_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(AppError):normalize_recording(b'x'*(LIMITS.video_bytes+1),t)

    def test_invalid_cloud_recording_rejected_before_model_loading(self):
        from skn_app.cloud_adapter import CloudAdapter
        adapter=CloudAdapter(lambda name:None)
        with patch.object(adapter.runtime,'load') as load:
            with self.assertRaises(AppError) as raised:adapter.process_media(b'fake','recorded_video','Balanced')
            self.assertEqual(raised.exception.code,'VIDEO_INVALID');load.assert_not_called()

    def test_cloud_recorded_video_without_previous_image(self):
        from skn_app.cloud_adapter import CloudAdapter
        adapter=CloudAdapter(lambda name:None)
        with patch('skn_app.recording_media.normalize_recording',return_value=b'normalized') as normalizer,patch('skn_app.cloud_adapter.process_video',return_value={}) as process:
            adapter.process_media(b'recorded','recorded_video','Balanced')
            normalizer.assert_called_once();process.assert_called_once()
            self.assertEqual(process.call_args.args[0],b'normalized')

    def test_variable_frame_timestamps_survive_webm_conversion(self):
        import av
        with tempfile.TemporaryDirectory() as t,patch('skn_app.recording_media.guard_memory'):
            path=Path(t)/'variable.webm'
            with av.open(str(path),'w',format='webm') as c:
                stream=c.add_stream('libvpx',rate=15);stream.width=160;stream.height=96
                stream.pix_fmt='yuv420p';stream.codec_context.time_base=Fraction(1,1000)
                for stamp in (0,20,100,130,200,280,330,400,480,530):
                    frame=av.VideoFrame.from_image(Image.new('RGB',(160,96),'gray'))
                    frame.pts=stamp;frame.time_base=Fraction(1,1000)
                    for packet in stream.encode(frame):c.mux(packet)
                for packet in stream.encode():c.mux(packet)
            output=normalize_recording(path.read_bytes(),t)
            with av.open(io.BytesIO(output)) as c:
                times=[float(f.time) for f in c.decode(video=0)]
                self.assertEqual(len(times),10);self.assertTrue(all(a<b for a,b in zip(times,times[1:])))


if __name__=='__main__':unittest.main()
