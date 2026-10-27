"""Synthetic media only; no camera, SDK, or model weights."""
import base64
import io
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from skn_app.config import LIMITS
from skn_app.errors import AppError
from skn_app.media import process_video,csv_bytes
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


class RecordingTests(unittest.TestCase):
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

    def test_cloud_recording_gate_prevents_model_loading(self):
        from skn_app.cloud_adapter import CloudAdapter
        adapter=CloudAdapter(lambda name:None)
        with patch.object(adapter.runtime,'load') as load:
            with self.assertRaises(AppError) as raised:adapter.process_media(b'fake','recorded_video','Balanced')
            self.assertEqual(raised.exception.code,'VIDEO_IMAGE_FIRST');load.assert_not_called()

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
