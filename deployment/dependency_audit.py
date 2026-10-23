"""Read-only package/capability audit; no SDK load/authentication, no install commands."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys


def audit():
    packages = {}
    for name in ('streamlit', 'inference-models', 'torch', 'torchvision', 'onnxruntime', 'onnx', 'numpy', 'Pillow', 'av'):
        try:packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:packages[name] = None
    providers = []
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
    except Exception:pass
    codec = False
    try:
        import av
        codec = av.codec.Codec('libx264', 'w').name == 'libx264'
    except Exception:pass
    return {'python': sys.version.split()[0], 'platform': sys.platform, 'packages': packages,
            'available_providers': providers, 'h264_encoder_available': codec,
            'model_loaded': False, 'cloud_runtime_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit()))
