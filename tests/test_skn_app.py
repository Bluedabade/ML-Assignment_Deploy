"""Synthetic app fixtures; tests never invoke real SDK models or read real credentials."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from skn_app.config import CLASSES, LIMITS, PROFILES
from skn_app.errors import AppError, safe_code
from skn_app.media import decode_image, process_image, process_video, video_metadata
from skn_app.resources import guard_memory, available_memory, memory_snapshot
from skn_app.secrets import authentication
from skn_app.runtime import ModelRuntime
from skn_app.cloud_adapter import CloudAdapter
from skn_app.local_adapter import LocalAdapter


def image_bytes(fmt='PNG', size=(64, 48)):
    output = io.BytesIO();Image.new('RGB', size, '#aaaabb').save(output, format=fmt);return output.getvalue()


def synthetic_video(folder, seconds=2):
    import av
    path = Path(folder)/'synthetic.mp4'
    with av.open(str(path), 'w') as container:
        stream = container.add_stream('libx264', rate=4);stream.width=160;stream.height=96;stream.pix_fmt='yuv420p'
        for i in range(seconds*4):
            frame = av.VideoFrame.from_image(Image.new('RGB', (160,96), (50+i,80,100)))
            for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    return path.read_bytes()


class FakeRuntime:
    def __init__(self):self.loads=0;self.calls=0
    def load(self):self.loads+=1
    def predict(self,image,profile):
        self.calls+=1
        return [dict(class_name='acne',confidence=.8,x1=1.,y1=2.,x2=10.,y2=12.)],.01


class AppTests(unittest.TestCase):
    def test_images_are_decoded_by_content_not_filename(self):
        for fmt in ('PNG','JPEG'):self.assertEqual(decode_image(image_bytes(fmt)).size,(64,48))
        for data in (b'not an image',image_bytes('GIF')):
            with self.assertRaises(AppError):decode_image(data)

    def test_size_pixel_and_exif_validation(self):
        with self.assertRaises(AppError):decode_image(b'x'*(LIMITS.image_bytes+1))
        with self.assertRaises(AppError):decode_image(image_bytes(size=(4096,2048)))
        im=Image.new('RGB',(30,20));exif=im.getexif();exif[274]=6;stream=io.BytesIO();im.save(stream,format='JPEG',exif=exif)
        self.assertEqual(decode_image(stream.getvalue()).size,(20,30))

    def test_shared_image_render_and_counts(self):
        runtime=FakeRuntime()
        with patch('skn_app.media.guard_memory'):
            result=process_image(image_bytes(),runtime,'Balanced')
        self.assertEqual(result['counts']['acne'],1);self.assertEqual(runtime.calls,1)
        self.assertEqual(Image.open(io.BytesIO(result['image_bytes'])).format,'PNG')
        self.assertIn(b'acne',result['csv_bytes'])

    def test_secret_environment_wins_even_when_empty(self):
        with patch.dict(os.environ,{'ROBOFLOW_API_KEY':'dummy-process'},clear=True):
            self.assertEqual(authentication('cloud',lambda name:'dummy-secret'),'dummy-process')
        with patch.dict(os.environ,{'ROBOFLOW_API_KEY':''},clear=True):
            with self.assertRaises(AppError):authentication('cloud',lambda name:'dummy-secret')

    def test_cloud_secret_injection_does_not_read_dotenv(self):
        with patch.dict(os.environ,{},clear=True),patch('dotenv.dotenv_values',side_effect=AssertionError('No dotenv in cloud')):
            self.assertEqual(authentication('cloud',lambda name:'dummy-cloud'),'dummy-cloud')
            self.assertNotIn('ROBOFLOW_API_KEY',os.environ)

    def test_dummy_local_dotenv_does_not_leak_or_change_file(self):
        with tempfile.TemporaryDirectory(prefix='skn-secret-test-') as folder:
            root=Path(folder);file=root/'.env';file.write_text('ROBOFLOW_API_KEY=dummy-local\nOTHER=dummy-other\n')
            before=file.read_bytes();captured=io.StringIO()
            with patch.dict(os.environ,{},clear=True),patch('skn_app.secrets.ROOT',root),contextlib.redirect_stdout(captured):
                self.assertEqual(authentication('local'),'dummy-local')
            self.assertEqual(file.read_bytes(),before);self.assertEqual(captured.getvalue(),'')

    def test_memory_telemetry_does_not_block_unknown_or_low_resources(self):
        for value in (None,0,100*1024**2,800*1024**2):
            with patch('skn_app.resources.available_memory',return_value=value):
                for options in ({'cold':True},{'video':True},{}):
                    result=guard_memory(**options)
                    self.assertEqual(result['available_bytes'],value)
                    self.assertEqual(result['required_bytes'],0)
                    self.assertFalse(result['enforced'])

    def test_linux_cgroup_limit_overrides_host_available(self):
        files={'/proc/meminfo':'MemAvailable: 8000000 kB\n','/sys/fs/cgroup/memory.max':'1073741824',
               '/sys/fs/cgroup/memory.current':'1000000000'}
        def read(path,*a,**kw):
            name=str(path).replace('\\','/')
            if name in files:return files[name]
            raise FileNotFoundError()
        with patch('skn_app.resources.sys.platform','linux'),patch.object(Path,'read_text',read):
            self.assertEqual(available_memory(),73741824)

    def test_cloud_concurrency_and_image_before_video(self):
        adapter=CloudAdapter(lambda name:'dummy')
        with self.assertRaises(AppError) as error:adapter.process_media(b'data','video','Balanced')
        self.assertEqual(error.exception.code,'VIDEO_IMAGE_FIRST')
        adapter.lock.acquire()
        try:
            with self.assertRaises(AppError) as error:adapter.process_media(b'data','image','Balanced')
            self.assertEqual(error.exception.code,'BUSY')
        finally:adapter.lock.release()

    def test_safe_linux_memory_snapshot_reports_limit_usage_without_environment(self):
        files={'/proc/meminfo':'MemAvailable: 8000000 kB\n',
               '/sys/fs/cgroup/memory.max':'1073741824',
               '/sys/fs/cgroup/memory.current':'1000000000',
               '/proc/self/statm':'100 20 0 0 0 0 0'}
        def read(path,*args,**kwargs):
            name=str(path).replace('\\','/')
            if name in files:return files[name]
            raise FileNotFoundError()
        with patch('skn_app.resources.sys.platform','linux'),patch.object(Path,'read_text',read),patch('skn_app.resources.os.sysconf',return_value=4096,create=True):
            result=memory_snapshot()
        self.assertEqual(result['cgroup_limit_bytes'],1073741824)
        self.assertEqual(result['cgroup_used_bytes'],1000000000)
        self.assertEqual(result['process_rss_bytes'],81920)
        self.assertEqual(result['available_bytes'],73741824)

    def test_cloud_job_temp_cleanup_on_error(self):
        adapter=CloudAdapter(lambda name:'dummy');adapter.image_verified=True;folders=[]
        def fail(data,runtime,profile,folder,progress):
            folders.append(Path(folder));(Path(folder)/'private.bin').write_bytes(b'private');raise AppError('VIDEO_INVALID')
        with patch('skn_app.cloud_adapter.process_video',side_effect=fail):
            with self.assertRaises(AppError):adapter.process_media(b'data','video','Balanced')
        self.assertFalse(folders[0].exists())

    def test_local_job_cleanup_and_no_shared_results(self):
        adapter=LocalAdapter();folders=[]
        def write(line):
            request=json.loads(line);folder=Path(request['folder']);folders.append(folder)
            (folder/'annotated.png').write_bytes(image_bytes());(folder/'detections.csv').write_bytes(b'class_name\n')
            adapter.messages.put(dict(event='result',job_id='0'*32,result={'counts':{'private':'other-session'}}))
            adapter.messages.put(dict(event='result',job_id=request['job_id'],result={'counts':dict.fromkeys(CLASSES,0)}))
        process=types.SimpleNamespace(stdin=types.SimpleNamespace(write=write,flush=lambda:None))
        with patch.object(adapter,'_start',side_effect=lambda:setattr(adapter,'process',process)):
            result=adapter.process_media(image_bytes(),'image','Balanced')
        adapter.process=None
        self.assertIn('image_bytes',result);self.assertFalse(folders[0].exists())
        self.assertNotIn('private',result['counts'])

    def test_video_samples_one_fps_and_exports_real_h264(self):
        import av
        with tempfile.TemporaryDirectory(prefix='skn-video-test-') as folder:
            data=synthetic_video(folder);runtime=FakeRuntime();progress=[]
            with patch('skn_app.media.guard_memory'):
                result=process_video(data,runtime,'Balanced',folder,lambda d,t:progress.append(d))
            self.assertEqual((runtime.loads,runtime.calls),(1,2));self.assertEqual(len(result['frames']),2)
            self.assertEqual([f['timestamp_seconds'] for f in result['frames']],[0.,1.])
            with av.open(io.BytesIO(result['video_bytes'])) as container:
                self.assertEqual(container.streams.video[0].codec_context.name,'h264')
                self.assertEqual(sum(1 for _ in container.decode(video=0)),2)
            self.assertEqual(progress,[1,2]);self.assertFalse(result['audio_included'])

    def test_interrupted_local_job_stops_own_worker_and_cleans_temp(self):
        adapter=LocalAdapter();folders=[]
        class Rerun(BaseException):pass
        def write(line):
            request=json.loads(line);folders.append(Path(request['folder']))
            adapter.messages.put(dict(event='progress',job_id=request['job_id'],done=1,total=2))
        process=types.SimpleNamespace(stdin=types.SimpleNamespace(write=write,flush=lambda:None))
        def interrupt(done,total):raise Rerun()
        with patch.object(adapter,'_start',side_effect=lambda:setattr(adapter,'process',process)), patch.object(adapter,'close') as close:
            with self.assertRaises(Rerun):adapter.process_media(b'video','video','Balanced',interrupt)
            close.assert_called_once()
        adapter.process=None
        self.assertFalse(folders[0].exists());self.assertFalse(adapter.lock.locked())

    def test_invalid_or_long_video_never_calls_model(self):
        with tempfile.TemporaryDirectory(prefix='skn-video-limit-test-') as folder:
            runtime=FakeRuntime()
            with self.assertRaises(AppError):process_video(b'bad',runtime,'Balanced',folder)
            with self.assertRaises(AppError):process_video(synthetic_video(folder,13),runtime,'Balanced',folder)
            self.assertEqual(runtime.loads,0);self.assertEqual(runtime.calls,0)

    def test_cloud_empty_cache_provisioning_and_model_reuse_with_dummy_loader(self):
        runtime=ModelRuntime('cloud',lambda:'dummy-key');calls=[]
        def loader(key,selected,adapter):
            self.assertEqual(key,'dummy-key');self.assertIsNone(adapter)
            cache=Path(os.environ['INFERENCE_HOME']);self.assertEqual(list(cache.iterdir()),[])
            package=cache/'package';package.mkdir();(package/'weights.onnx').write_bytes(b'synthetic-model')
            selected.append(str(package));calls.append(1)
            return types.SimpleNamespace(_session=types.SimpleNamespace(get_providers=lambda:['CPUExecutionProvider']),class_names=list(__import__('skn_app.config',fromlist=['MAPPING']).MAPPING))
        try:
            with patch('skn_app.runtime.guard_memory'),patch('skn_app.runtime.load_official',side_effect=loader),patch('skn_app.runtime.WEIGHTS_SHA256',hashlib.sha256(b'synthetic-model').hexdigest()),patch.dict(os.environ,{},clear=True):
                runtime.load();runtime.load()
            self.assertEqual(len(calls),1);self.assertEqual(runtime.model_loads,1)
        finally:runtime.close()

    def test_model_failure_is_sanitized_and_not_retried(self):
        runtime=ModelRuntime('cloud',lambda:'dummy-key')
        try:
            with patch('skn_app.runtime.guard_memory'),patch('skn_app.runtime.load_official',side_effect=RuntimeError('private-key-in-url')) as loader:
                for _ in range(2):
                    with self.assertRaises(AppError) as error:runtime.load()
                    self.assertEqual(error.exception.code,'MODEL_NOT_READY');self.assertNotIn('private',str(error.exception))
                self.assertEqual(loader.call_count,1)
        finally:runtime.close()

    def test_profile_mapping_uses_fixed_nms_and_canonical_classes(self):
        runtime=ModelRuntime('cloud',lambda:'unused');calls=[]
        class Model:
            class_names=['Acne','Wrinkles','Dark Spots','Open Pores','Dry Skin']
            def __call__(self,image,**kw):
                calls.append(kw)
                return [types.SimpleNamespace(class_id=np.array([0,1,2,3,4]),confidence=np.array([.3,.3,.3,.3,.9]),xyxy=np.tile([1,2,20,30],(5,1)))]
        runtime.model=Model()
        try:
            balanced,_=runtime.predict(Image.new('RGB',(64,48)),'Balanced')
            precision,_=runtime.predict(Image.new('RGB',(64,48)),'Precision-focused')
            self.assertEqual(len(balanced),4);self.assertEqual(len(precision),3)
            self.assertEqual(calls[0],dict(confidence=.001,iou_threshold=.3,max_detections=300,class_agnostic_nms=False))
        finally:runtime.close()

    def test_unknown_errors_never_export_raw_messages(self):
        self.assertEqual(safe_code(RuntimeError('private-api-key')), 'INFERENCE_FAILED')


if __name__=='__main__':unittest.main()
