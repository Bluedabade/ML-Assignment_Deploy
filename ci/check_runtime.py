"""Capability probes on installed Linux dependencies; no model constructor is called."""
import importlib
import importlib.metadata as metadata
import json
import platform
import sys
from .safety import install_guard, forbid_model


def check():
    install_guard()
    for name in ('skn_app.config', 'skn_app.errors', 'skn_app.resources', 'skn_app.secrets',
                 'skn_app.media', 'skn_app.runtime', 'skn_app.cloud_adapter', 'skn_app.ui',
                 'skn_app.video_recorder', 'skn_app.recording_media'):
        importlib.import_module(name)
    from skn_app import runtime
    runtime.load_official = forbid_model
    import onnxruntime as ort
    import pyvips
    import cv2
    import av
    import torch
    import torchvision
    from inference_models import AutoModel
    AutoModel.from_pretrained = staticmethod(forbid_model)
    if 'CPUExecutionProvider' not in ort.get_available_providers():
        raise RuntimeError('CPU_PROVIDER_MISSING')
    if torch.version.cuda is not None:
        raise RuntimeError('NON_CPU_TORCH_INSTALLED')
    if pyvips.Image.black(2, 2).width != 2:
        raise RuntimeError('LIBVIPS_OPERATION_FAILED')
    if av.codec.Codec('libx264', 'w').name != 'libx264':
        raise RuntimeError('H264_ENCODER_MISSING')
    return {'status': 'CAPABILITIES_PASSED_NO_MODEL', 'python': platform.python_version(),
            'platform': sys.platform, 'providers': ort.get_available_providers(),
            'libvips_version': '.'.join(str(pyvips.version(n)) for n in range(3)),
            'pyvips_api_mode': pyvips.API_mode,
            'packages': {name: metadata.version(name) for name in
                         ('streamlit', 'inference-models', 'onnxruntime', 'torch', 'torchvision', 'pyvips', 'av')},
            'model_load_calls': 0, 'external_network_allowed': False}


if __name__ == '__main__':
    try:
        print(json.dumps(check()))
    except Exception:
        print(json.dumps({'status': 'CAPABILITY_CHECK_FAILED', 'model_load_calls': 0}))
        raise SystemExit(1)
