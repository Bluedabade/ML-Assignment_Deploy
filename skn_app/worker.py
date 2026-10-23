"""Private local NDJSON worker; no shell/media logs."""
import json
from pathlib import Path
import sys
import tempfile
from .config import LIMITS
from .errors import AppError, safe_code
from .media import process_image, process_video
from .runtime import ModelRuntime
from .secrets import authentication


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def main():
    import os
    runtime = ModelRuntime('local', lambda: authentication('local'), os.environ.get('SKN_LOCAL_MODEL_CACHE'))
    try:
        for line in sys.stdin:
            job_id = None
            try:
                request = json.loads(line)
                if request.get('operation') == 'shutdown':
                    break
                job_id = request.get('job_id')
                if not isinstance(job_id,str) or len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):
                    raise AppError('INPUT_INVALID')
                folder = Path(request['folder'])
                if (folder.resolve() != folder or folder.parent.resolve() != Path(tempfile.gettempdir()).resolve()
                        or not folder.name.startswith('skn-job-') or not folder.is_dir()):
                    raise AppError('INPUT_INVALID')
                kind, profile = request['kind'], request['profile']
                if kind not in ('image', 'video'):
                    raise AppError('INPUT_INVALID')
                source = folder/'upload.bin'
                maximum = LIMITS.image_bytes if kind == 'image' else LIMITS.video_bytes
                if source.is_symlink() or not source.is_file() or source.stat().st_size > maximum:
                    raise AppError('INPUT_INVALID')
                data = source.read_bytes()
                result = process_image(data, runtime, profile) if kind == 'image' else process_video(
                    data, runtime, profile, folder, lambda done, total: emit(dict(event='progress', job_id=job_id, done=done, total=total)))
                for key, name in [('image_bytes', 'annotated.png'), ('video_bytes', 'sampled.mp4'), ('csv_bytes', 'detections.csv')]:
                    if key in result:
                        (folder/name).write_bytes(result.pop(key))
                result.update(model_loads=runtime.model_loads, model_load_seconds=runtime.load_seconds,
                    inference_calls=runtime.inference_calls, backend='ONNX CPU / CPUExecutionProvider')
                emit(dict(event='result', job_id=job_id, result=result))
            except Exception as error:
                emit(dict(event='error', job_id=job_id, code=safe_code(error)))
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
