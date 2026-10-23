"""Portable app configuration; Windows interpreter discovery belongs to local_adapter."""
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'skn-1/2'
CLASSES = ('acne', 'wrinkle', 'dark_spot', 'enlarged_pore')
MAPPING = {'Acne': 'acne', 'Wrinkles': 'wrinkle', 'Dark Spots': 'dark_spot', 'Open Pores': 'enlarged_pore'}
PROFILES = {
    'Balanced': dict.fromkeys(CLASSES, .25),
    'Precision-focused': dict(zip(CLASSES, (.25, .45, .275, .30))),
}


def mode():
    value = os.getenv('SKN_APP_MODE', 'local' if os.name == 'nt' else 'cloud')
    if value not in ('local', 'cloud'):
        raise ValueError('Invalid app mode')
    return value


@dataclass(frozen=True)
class Limits:
    image_bytes: int = 5*1024**2
    image_pixels: int = 4*1024**2
    video_bytes: int = 20*1024**2
    video_seconds: int = 12
    video_pixels: int = 1280*720
    video_long_side: int = 1280
    sampled_fps: int = 1
    job_seconds: int = 120
    result_ttl_seconds: int = 600


LIMITS = Limits()
