"""Windows-only discovery and one persistent local SKN worker."""
import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid
from .config import ROOT, LIMITS
from .errors import AppError
from .media import validate_bytes


class LocalAdapter:
    def __init__(self):
        self.python = Path(os.getenv('SKN_PYTHON', str(ROOT.parent/(ROOT.name+'-roboflow-env')/'Scripts/python.exe')))
        self.cache = Path(os.getenv('SKN_LOCAL_MODEL_CACHE', str(self.python.parent.parent/'model_cache')))
        self.process = None
        self.messages = queue.Queue()
        self.lock = threading.Lock()
        atexit.register(self.close)

    def _start(self):
        if self.process is not None and self.process.poll() is None:
            return
        if not self.python.is_file():
            raise AppError('LOCAL_ENV_MISSING')
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', SKN_LOCAL_MODEL_CACHE=str(self.cache))
        self.process = subprocess.Popen([str(self.python), '-B', '-m', 'skn_app.worker'], cwd=ROOT,
            env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding='utf-8', text=True, bufsize=1, shell=False,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue()
        stream, messages = self.process.stdout, self.messages
        def read():
            for line in stream:
                try:
                    item = json.loads(line)
                    if item.get('event') in ('progress', 'result', 'error'):
                        messages.put(item)
                except (ValueError, AttributeError):
                    pass
            messages.put(dict(event='error', code='INFERENCE_FAILED'))
        threading.Thread(target=read, daemon=True).start()

    def process_media(self, data, kind, profile, progress=lambda done, total: None):
        validate_bytes(data, kind)
        if not self.lock.acquire(blocking=False):
            raise AppError('BUSY')
        try:
            self._start()
            with tempfile.TemporaryDirectory(prefix='skn-job-') as temp:
                folder = Path(temp);(folder/'upload.bin').write_bytes(data)
                job_id = uuid.uuid4().hex
                self.process.stdin.write(json.dumps(dict(folder=str(folder), kind=kind, profile=profile,job_id=job_id))+'\n')
                self.process.stdin.flush()
                deadline = time.monotonic()+LIMITS.job_seconds+30
                while True:
                    try:
                        item = self.messages.get(timeout=max(.01, deadline-time.monotonic()))
                    except queue.Empty:
                        self.close();raise AppError('JOB_TIMEOUT') from None
                    if item.get('job_id') != job_id:
                        if item.get('job_id') is None and item['event']=='error':raise AppError('INFERENCE_FAILED')
                        continue  # A response from an aborted job can never enter another session.
                    if item['event'] == 'progress':
                        progress(item['done'], item['total'])
                    elif item['event'] == 'error':
                        raise AppError(item.get('code'))
                    else:
                        result = item['result']
                        for key, name in [('image_bytes', 'annotated.png'), ('video_bytes', 'sampled.mp4'), ('csv_bytes', 'detections.csv')]:
                            path = folder/name
                            if path.is_file() and not path.is_symlink():
                                result[key] = path.read_bytes()
                        if ('image_bytes' if kind == 'image' else 'video_bytes') not in result or 'csv_bytes' not in result:
                            raise AppError('INFERENCE_FAILED')
                        return result
        except AppError:
            raise
        except Exception:
            self.close();raise AppError('INFERENCE_FAILED') from None
        except BaseException:
            # Streamlit reruns can interrupt progress callbacks. Stop our own job before unlocking.
            self.close();raise
        finally:
            self.lock.release()

    def close(self):
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            try:
                process.stdin.write('{"operation":"shutdown"}\n');process.stdin.flush();process.wait(timeout=3)
            except Exception:
                process.terminate()
                try:process.wait(timeout=3)
                except Exception:pass
