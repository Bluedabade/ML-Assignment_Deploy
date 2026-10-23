"""One lazy cached model and one concurrent job in the Linux app process."""
import tempfile
import threading
from .errors import AppError
from .media import process_image, process_video
from .runtime import ModelRuntime
from .secrets import authentication


class CloudAdapter:
    def __init__(self, secrets_reader):
        self.runtime = ModelRuntime('cloud', lambda: authentication('cloud', secrets_reader))
        self.lock = threading.Lock()
        self.image_verified = False

    def process_media(self, data, kind, profile, progress=lambda done, total: None):
        if not self.lock.acquire(blocking=False):
            raise AppError('BUSY')
        try:
            if kind == 'image':
                result = process_image(data, self.runtime, profile);self.image_verified = True
            elif kind == 'video':
                if not self.image_verified:raise AppError('VIDEO_IMAGE_FIRST')
                with tempfile.TemporaryDirectory(prefix='skn-job-') as folder:
                    result = process_video(data, self.runtime, profile, folder, progress)
            else:raise AppError('INPUT_INVALID')
            result.update(model_loads=self.runtime.model_loads, model_load_seconds=self.runtime.load_seconds,
                inference_calls=self.runtime.inference_calls, backend='ONNX CPU / CPUExecutionProvider')
            return result
        except AppError:raise
        except Exception:raise AppError('INFERENCE_FAILED') from None
        finally:self.lock.release()
