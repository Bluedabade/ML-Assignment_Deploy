"""Session-only candidate cache and pure image presentation. Never loads a model."""
import hashlib
import io
import json
import math
from collections.abc import Mapping
from numbers import Real
from PIL import Image, ImageDraw, ImageFont

from .config import CLASSES, PROFILES, MODEL_ID, LIMITS, MAPPING
from .errors import AppError
from .media import COLORS, csv_bytes
from .runtime import WEIGHTS_SHA256

CUSTOM = 'Custom'
CACHE_SLOT = 'image_candidate_cache'
LABEL_MODES = ('class_percent', 'percent', 'none')
CANDIDATE_FIELDS = {'class_name','confidence','x1','y1','x2','y2'}
INFERENCE_IDENTITY = dict(model_id=MODEL_ID, weights_sha256=WEIGHTS_SHA256,
    backend='ONNX CPU', confidence=.001, iou_threshold=.3, max_detections=300,
    class_agnostic_nms=False, class_mapping=dict(MAPPING), preprocessing='original-metadata/exif-RGB-to-BGR/v1')


def display_thresholds(profile, threshold=.25):
    if profile in PROFILES:return dict(PROFILES[profile])
    if profile != CUSTOM or not math.isfinite(threshold) or not .10 <= threshold <= .90:
        raise AppError('INPUT_INVALID')
    return dict.fromkeys(CLASSES, float(threshold))


def filter_detections(candidates, thresholds):
    limits = dict(thresholds) if isinstance(thresholds, Mapping) else dict.fromkeys(CLASSES, thresholds)
    if set(limits) != set(CLASSES) or any(not math.isfinite(v) or not .001 <= v <= 1 for v in limits.values()):
        raise AppError('INPUT_INVALID')
    result = []
    for row in candidates:
        if (not isinstance(row,Mapping) or set(row) != CANDIDATE_FIELDS or row.get('class_name') not in CLASSES or
                not all(isinstance(row[k],Real) and not isinstance(row[k],bool) and math.isfinite(row[k]) for k in ('confidence','x1','y1','x2','y2')) or
                not .001 <= row['confidence'] <= 1 or row['x2'] <= row['x1'] or row['y2'] <= row['y1']):
            raise AppError('INPUT_INVALID')
        if row['confidence'] >= limits[row['class_name']]:result.append(dict(row))
    return result


def summarize_counts(rows):
    return {name: sum(row['class_name'] == name for row in rows) for name in CLASSES}


def render_annotated(image, rows, opacity=.65, label_mode='class_percent'):
    if not .1 <= opacity <= 1 or label_mode not in LABEL_MODES:raise AppError('INPUT_INVALID')
    base = image.convert('RGBA')
    layer = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(layer)
    for row in rows:
        rgb = tuple(bytes.fromhex(COLORS[row['class_name']][1:]))
        draw.rectangle([row[k] for k in ('x1','y1','x2','y2')],
                       outline=(*rgb, round(255*opacity)), width=max(2,image.width//300))
    rendered = Image.alpha_composite(base, layer).convert('RGB')
    if label_mode != 'none':
        draw = ImageDraw.Draw(rendered)
        font = ImageFont.load_default()
        for row in rows:
            label = f"{row['confidence']:.0%}"
            # Built-in Pillow font is portable; Thai legend lives in the web UI.
            if label_mode == 'class_percent':label = row['class_name']+' '+label
            draw.text((row['x1'],max(0,row['y1']-14)),label,font=font,fill=COLORS[row['class_name']],stroke_width=1,stroke_fill='black')
    return rendered


def build_image_result(image, candidates, thresholds, opacity=.65, label_mode='class_percent'):
    rows = filter_detections(candidates, thresholds)
    output = io.BytesIO()
    render_annotated(image, rows, opacity, label_mode).save(output, format='PNG')
    return dict(predictions=rows, counts=summarize_counts(rows), image_bytes=output.getvalue(),
                csv_bytes=csv_bytes([dict(row,timestamp_seconds=0.) for row in rows]))


def candidate_cache_key(data, kind='image'):
    identity = dict(INFERENCE_IDENTITY, file_sha256=hashlib.sha256(data).hexdigest(), kind=kind)
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()


def make_image_cache(data, result, now):
    if not isinstance(data, bytes) or not data or len(data) > LIMITS.image_bytes or len(result['candidates']) > 300:
        raise AppError('INPUT_INVALID')
    # One compressed input, one candidate collection; no global image cache or retained rendered copies.
    return dict(key=candidate_cache_key(data), created_at=now, original_bytes=data,
        candidates=tuple(filter_detections(result['candidates'],.001)),
        metadata={k:result[k] for k in ('inference_seconds','model_loads','model_load_seconds','inference_calls','backend') if k in result})


def get_image_cache(state, key=None, now=0):
    cache = state.get(CACHE_SLOT)
    if cache is None:return None
    if (key is not None and cache['key'] != key) or not 0 <= now-cache['created_at'] < LIMITS.result_ttl_seconds:
        state.pop(CACHE_SLOT, None);return None
    return cache


def preview_thumbnail(image, max_size=(960,480)):
    """Copy/contain for display only; source and original-resolution export are preserved."""
    if len(max_size)!=2 or min(max_size)<=0:raise ValueError('INVALID_PREVIEW_SIZE')
    result=image.copy()
    result.thumbnail(max_size, Image.Resampling.LANCZOS)
    return result
