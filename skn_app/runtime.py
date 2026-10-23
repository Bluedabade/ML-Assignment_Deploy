"""Lazy official SDK loading. Media is passed only to the local ONNX model."""
import atexit
import contextlib
import hashlib
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from .config import MODEL_ID, MAPPING, PROFILES
from .errors import AppError
from .resources import guard_memory

WEIGHTS_SHA256 = '98feb0d9fe13726934c0dc810eca950b429c76e740beb564be40786cff3f80c6'


@contextlib.contextmanager
def quiet_sdk():
    """Discard Python and native SDK logs; never persist raw SDK responses/errors."""
    prior = logging.root.manager.disable
    first, second = os.dup(1), os.dup(2)
    try:
        logging.disable(logging.CRITICAL)
        with open(os.devnull, 'w') as sink:
            sys.stdout.flush();sys.stderr.flush()
            os.dup2(sink.fileno(), 1);os.dup2(sink.fileno(), 2)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
    finally:
        os.dup2(first, 1);os.dup2(second, 2);os.close(first);os.close(second)
        logging.disable(prior)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def load_official(key, selected, adapter=None):
    from inference_models import AutoModel
    from inference_models.models.auto_loaders import core
    manager = patch.object(core, 'download_files_to_directory', adapter) if adapter else contextlib.nullcontext()
    with manager:
        return AutoModel.from_pretrained(MODEL_ID, api_key=key, backend='onnx', device='cpu',
            onnx_execution_providers=['CPUExecutionProvider'], verbose=False,
            allow_untrusted_packages=False, allow_local_code_packages=False,
            allow_loading_dependency_models=False, point_model_directory=selected.append)


class ModelRuntime:
    def __init__(self, mode, key_provider, local_cache=None):
        self.mode, self.key_provider, self.local_cache = mode, key_provider, local_cache
        self.model = None
        self.failed = False
        self.storage = None
        self.load_seconds = None
        self.model_loads = 0
        self.inference_calls = 0
        atexit.register(self.close)

    def close(self):
        self.model = None
        if self.storage is not None:
            self.storage.cleanup();self.storage = None

    def load(self):
        if self.model is not None:
            return
        if self.failed:
            raise AppError('MODEL_NOT_READY')
        guard_memory(cold=True)
        key = self.key_provider()
        self.storage = tempfile.TemporaryDirectory(prefix='skn-runtime-')
        cache = Path(self.storage.name)/'model_cache'
        adapter = None
        original_snapshot = None
        if self.mode == 'local':
            try:
                # Only the Windows/local adapter needs existing audit helpers. Cloud never imports these.
                from tools.skn1_optimization.runtime_cache import prepare_runtime_cache, cache_snapshot
                from tools.skn1_optimization.model_load import cached_downloads_only, install_protection
                source = Path(self.local_cache).resolve()
                packages = list(source.glob('models-cache/v2-skn-1-2-*/*/model_config.json'))
                if len(packages) != 1:
                    raise AppError('LOCAL_CACHE_INVALID')
                original_snapshot = cache_snapshot(source)
                prepare_runtime_cache(source, packages[0].parent, cache)
                adapter = cached_downloads_only(cache)
                from .config import ROOT
                install_protection(ROOT, source, Path(self.storage.name))
            except Exception:
                self.storage.cleanup();self.storage = None
                raise AppError('LOCAL_CACHE_INVALID') from None
        else:
            cache.mkdir()
        if any(n == 'inference_models' or n.startswith('inference_models.') for n in sys.modules):
            raise AppError('MODEL_NOT_READY')
        os.environ['INFERENCE_HOME'] = str(cache)
        os.environ['DEFAULT_DEVICE'] = 'cpu'
        os.environ['ONNXRUNTIME_EXECUTION_PROVIDERS'] = 'CPUExecutionProvider'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        selected = []
        try:
            with quiet_sdk():
                start = time.perf_counter()
                self.model_loads += 1
                model = load_official(key, selected, adapter)
                self.load_seconds = time.perf_counter()-start
            if (model._session.get_providers() != ['CPUExecutionProvider'] or not set(MAPPING) <= set(model.class_names)
                    or not selected or not Path(selected[-1]).resolve().is_relative_to(cache.resolve())
                    or digest(Path(selected[-1])/'weights.onnx') != WEIGHTS_SHA256):
                raise AppError('MODEL_NOT_READY')
            self.model = model
        except Exception:
            self.failed = True;self.close()
            raise AppError('MODEL_NOT_READY') from None
        finally:
            # Never mutate or repair protected source weights/cache.
            if original_snapshot is not None and cache_snapshot(source) != original_snapshot:
                self.failed = True;self.close()
                raise AppError('LOCAL_CACHE_INVALID')

    def predict(self, image, profile):
        if profile not in PROFILES:
            raise AppError('INPUT_INVALID')
        self.load()
        import numpy as np
        # Shared pipeline supplies EXIF-normalized RGB; SKN expects BGR ndarray.
        frame = np.ascontiguousarray(np.asarray(image.convert('RGB'))[:, :, ::-1])
        with quiet_sdk():
            start = time.perf_counter()
            output = self.model(frame, confidence=.001, iou_threshold=.3, max_detections=300, class_agnostic_nms=False)[0]
            seconds = time.perf_counter()-start
        self.inference_calls += 1
        if len(output.confidence) > 300:
            raise AppError('INFERENCE_FAILED')
        rows = []
        for cid, confidence, box in zip(output.class_id.tolist(), output.confidence.tolist(), output.xyxy.tolist()):
            label = MAPPING.get(self.model.class_names[int(cid)])
            if label is None or confidence < PROFILES[profile][label]:
                continue
            if not np.isfinite([confidence, *box]).all() or not .001 <= confidence <= 1:
                raise AppError('INFERENCE_FAILED')
            x1, y1, x2, y2 = map(float, box)
            x1, x2 = max(0., x1), min(float(image.width), x2)
            y1, y2 = max(0., y1), min(float(image.height), y2)
            if x2 > x1 and y2 > y1:
                rows.append(dict(class_name=label, confidence=float(confidence), x1=x1, y1=y1, x2=x2, y2=y2))
        return rows, seconds
