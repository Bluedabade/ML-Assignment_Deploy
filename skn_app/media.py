"""Bounded image/video parsing and browser-compatible sampled-video exports."""
from collections import Counter
import csv
import io
import math
import struct
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageOps

from .config import CLASSES, LIMITS, PROFILES
from .errors import AppError
from .resources import guard_memory

COLORS = {'acne': '#ef5350', 'wrinkle': '#ffc857', 'dark_spot': '#ad7aff', 'enlarged_pore': '#29c7c9'}


def validate_bytes(data, kind):
    maximum = LIMITS.image_bytes if kind == 'image' else LIMITS.video_bytes
    if not data or len(data) > maximum:
        raise AppError('UPLOAD_TOO_LARGE')


def decode_image(data):
    validate_bytes(data, 'image')
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.format not in ('JPEG', 'PNG'):
                raise AppError('IMAGE_INVALID')
            if original.width*original.height > LIMITS.image_pixels or max(original.size) > 4096:
                raise AppError('IMAGE_DIMENSIONS')
            original.verify()
        with Image.open(io.BytesIO(data)) as original:
            return ImageOps.exif_transpose(original).convert('RGB')
    except AppError:
        raise
    except Exception:
        raise AppError('IMAGE_INVALID') from None


def annotate(image, rows, timestamp=None):
    rendered = image.copy()
    draw = ImageDraw.Draw(rendered)
    for row in rows:
        color = COLORS[row['class_name']]
        draw.rectangle([row[k] for k in ('x1', 'y1', 'x2', 'y2')], outline=color, width=max(2, image.width//300))
        draw.text((row['x1'], max(0, row['y1']-14)), f"{row['class_name']} {row['confidence']:.0%}", fill=color, stroke_width=1, stroke_fill='black')
    if timestamp is not None:
        draw.rectangle([0, 0, 220, 25], fill='black')
        draw.text((6, 6), f'Sampled frame | t={timestamp:.2f}s', fill='white')
    return rendered


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    fields = ['timestamp_seconds', 'class_name', 'confidence', 'x1', 'y1', 'x2', 'y2']
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def process_image(data, runtime, profile):
    if profile not in PROFILES:raise AppError('INPUT_INVALID')
    from .presentation import filter_detections
    image = decode_image(data)
    runtime.load();guard_memory()
    candidates, seconds = runtime.predict_candidates(image)
    rows = filter_detections(candidates, PROFILES[profile])
    output = io.BytesIO();annotate(image, rows).save(output, format='PNG')
    return dict(predictions=rows, counts={c: sum(r['class_name']==c for r in rows) for c in CLASSES},
        inference_seconds=seconds, width=image.width, height=image.height, image_bytes=output.getvalue(),
        csv_bytes=csv_bytes([dict(r, timestamp_seconds=0.) for r in rows]), candidates=candidates,
        candidate_stage='POST_NMS_CAP_MAPPING_GEOMETRY')


def video_metadata(path):
    from .runtime import quiet_sdk
    with quiet_sdk():
        return _video_metadata(path)


def video_rotation(frame, metadata=None, fallback=0):
    """Read a pure quarter-turn; PyAV DISPLAYMATRIX angles are counterclockwise.

    Validate the whole matrix, not only its angle: flips, shear, scale and
    perspective cannot safely be treated as a rotation. Translation only
    moves the display origin and is removed when fitting the upright frame.
    Legacy rotate tags use clockwise degrees; a display matrix takes priority.
    """
    matrices = [x for x in frame.side_data if 'DISPLAYMATRIX' in str(x.type).upper()]
    if len(matrices)>1:raise AppError('VIDEO_ROTATION')
    if matrices:
        raw=bytes(matrices[0])
        if len(raw)!=36:raise AppError('VIDEO_ROTATION')
        matrix=struct.unpack('=9i',raw)
        angle=float(frame.rotation)
    else:
        tag=(metadata or {}).get('rotate','')
        try:angle=-float(tag) if tag else float(fallback)
        except (ValueError,TypeError):raise AppError('VIDEO_ROTATION') from None
    if not math.isfinite(angle) or abs(angle/90-round(angle/90))>1e-5:
        raise AppError('VIDEO_ROTATION')
    rotation=int(round(angle/90)*90)%360
    if matrices:
        a,b,c,d={0:(1,0,0,1),90:(0,-1,1,0),180:(-1,0,0,-1),270:(0,1,-1,0)}[rotation]
        expected={0:a*65536,1:b*65536,2:0,3:c*65536,4:d*65536,5:0,8:1<<30}
        if any(abs(matrix[i]-value)>2 for i,value in expected.items()):raise AppError('VIDEO_ROTATION')
    return rotation


def upright_video_image(frame, rotation):
    """Lossless pixel transpose before prediction; no crop, scale or box remap."""
    image=frame.to_image().convert('RGB')
    operation={90:Image.Transpose.ROTATE_90,180:Image.Transpose.ROTATE_180,270:Image.Transpose.ROTATE_270}.get(rotation)
    return image.transpose(operation) if operation is not None else image


def _video_metadata(path):
    try:
        import av
        with av.open(str(path)) as container:
            if 'mp4' not in container.format.name.split(',') and 'mov' not in container.format.name.split(','):
                raise AppError('VIDEO_INVALID')
            if len(container.streams.video) != 1:
                raise AppError('VIDEO_INVALID')
            stream = container.streams.video[0]
            width, height = stream.codec_context.width, stream.codec_context.height
            duration = float(stream.duration*stream.time_base) if stream.duration is not None else (
                container.duration/av.time_base if container.duration is not None else None)
            rate = float(stream.average_rate) if stream.average_rate else 0.
            if (duration is None or not math.isfinite(duration) or duration <= 0 or duration > LIMITS.video_seconds+.01
                    or min(width, height) <= 0 or width*height > LIMITS.video_pixels
                    or max(width, height) > LIMITS.video_long_side or not 0 < rate <= 60):
                raise AppError('VIDEO_LIMITS')
            stream.thread_count=1
            guard_memory(video=True)
            first=next(quiet_decode(container),None)
            if first is None or (first.width,first.height)!=(width,height):raise AppError('VIDEO_INVALID')
            rotation=video_rotation(first,stream.metadata)
            display_width,display_height=(height,width) if rotation in (90,270) else (width,height)
            av.codec.Codec('libx264', 'w')
            return dict(width=display_width, height=display_height, source_width=width, source_height=height,
                rotation_degrees_ccw=rotation, duration_seconds=duration, source_fps=rate,
                source_codec=stream.codec_context.name, maximum_samples=math.ceil(duration),
                maximum_decoded_frames=math.ceil(duration*rate*1.5)+8)
    except AppError:
        raise
    except ImportError:
        raise AppError('VIDEO_CODEC') from None
    except Exception:
        raise AppError('VIDEO_INVALID') from None


def quiet_decode(container):
    from .runtime import quiet_sdk
    decoder=iter(container.decode(video=0))
    while True:
        with quiet_sdk():
            try:frame=next(decoder)
            except StopIteration:return
        yield frame


def process_video(data, runtime, profile, folder, progress=lambda done, total: None):
    validate_bytes(data, 'video')
    if profile not in PROFILES:raise AppError('INPUT_INVALID')
    # Require an ISO BMFF ftyp header; suffix supplied by the user is never a path.
    if len(data) < 12 or data[4:8] != b'ftyp':
        raise AppError('VIDEO_INVALID')
    import av
    folder = Path(folder)
    source, destination = folder/'input.mp4', folder/'sampled.mp4'
    source.write_bytes(data)
    metadata = video_metadata(source)
    runtime.load();guard_memory(video=True)
    rows, frames, timings = [], [], []
    started = time.monotonic()
    with av.open(str(source)) as incoming, av.open(str(destination), 'w', format='mp4', options={'movflags': '+faststart'}) as outgoing:
        stream = outgoing.add_stream('libx264', rate=1)
        # yuv420p requires even dimensions. At most one pixel is padded at right/bottom, not scaled.
        stream.width = metadata['width']+(metadata['width']%2)
        stream.height = metadata['height']+(metadata['height']%2)
        stream.pix_fmt = 'yuv420p';stream.options = {'preset': 'veryfast', 'crf': '23', 'profile': 'baseline'}
        next_sample, first_time, decoded, last_timestamp = 0., None, 0, -1.
        for frame in quiet_decode(incoming):
            rotation=video_rotation(frame,incoming.streams.video[0].metadata,metadata['rotation_degrees_ccw'])
            if rotation!=metadata['rotation_degrees_ccw']:raise AppError('VIDEO_ROTATION')
            if (frame.width,frame.height)!=(metadata['source_width'],metadata['source_height']):raise AppError('VIDEO_INVALID')
            if time.monotonic()-started > LIMITS.job_seconds:
                raise AppError('JOB_TIMEOUT')
            raw_time = float(frame.time) if frame.time is not None else decoded/metadata['source_fps']
            decoded += 1
            if decoded > metadata['maximum_decoded_frames']:raise AppError('VIDEO_LIMITS')
            if first_time is None:
                first_time = raw_time
            timestamp = raw_time-first_time
            if not math.isfinite(timestamp) or timestamp < -.001 or timestamp < last_timestamp-.001:
                raise AppError('VIDEO_INVALID')
            last_timestamp=timestamp
            if timestamp >= metadata['duration_seconds'] or len(frames) >= LIMITS.video_seconds:
                break
            if timestamp+1e-6 < next_sample:
                continue
            guard_memory(video=True)
            image = upright_video_image(frame,rotation)
            if image.size != (metadata['width'], metadata['height']):
                raise AppError('VIDEO_INVALID')
            predictions, seconds = runtime.predict(image, profile)
            rows.extend(dict(r, timestamp_seconds=timestamp) for r in predictions)
            if not predictions:
                rows.append(dict(timestamp_seconds=timestamp, class_name='', confidence='', x1='', y1='', x2='', y2=''))
            rendered = annotate(image, predictions, timestamp)
            if rendered.size != (stream.width, stream.height):
                padded = Image.new('RGB', (stream.width, stream.height));padded.paste(rendered);rendered = padded
            output_frame = av.VideoFrame.from_image(rendered)
            for packet in stream.encode(output_frame):
                outgoing.mux(packet)
            frames.append(dict(timestamp_seconds=timestamp, detections=len(predictions)))
            timings.append(seconds);next_sample = math.floor(timestamp)+1.
            progress(len(frames), metadata['maximum_samples'])
        for packet in stream.encode():
            outgoing.mux(packet)
    if not frames:
        raise AppError('VIDEO_INVALID')
    if destination.stat().st_size>LIMITS.video_bytes:raise AppError('RESOURCE_LIMITED')
    # Verify actual output codec/container before returning browser download bytes.
    with av.open(str(destination)) as check:
        if check.streams.video[0].codec_context.name != 'h264':
            raise AppError('VIDEO_CODEC')
        if sum(1 for _ in check.decode(video=0)) != len(frames):
            raise AppError('VIDEO_CODEC')
    counts = Counter(r['class_name'] for r in rows if r['class_name'])
    return dict(metadata=metadata, frames=frames, predictions=rows, counts={c: counts[c] for c in CLASSES},
        inference_seconds=sum(timings), mean_inference_seconds=sum(timings)/len(timings),
        processing_seconds=time.monotonic()-started, sampled_fps=1, audio_included=False,
        video_bytes=destination.read_bytes(), csv_bytes=csv_bytes(rows))
