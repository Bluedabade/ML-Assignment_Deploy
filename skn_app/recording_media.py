"""Validate a browser recording and, for WebM only, normalize inside the job folder."""
import math
from fractions import Fraction
from pathlib import Path
import time
from .config import LIMITS
from .errors import AppError
from .media import validate_bytes, video_metadata, quiet_decode
from .resources import guard_memory
from .runtime import quiet_sdk


def normalize_recording(data, folder):
    validate_bytes(data,'video')
    mp4=len(data)>=12 and data[4:8]==b'ftyp'
    webm=data.startswith(b'\x1aE\xdf\xa3')
    if not (mp4 or webm):raise AppError('VIDEO_INVALID')
    try:
        with quiet_sdk():return _normalize(data,Path(folder),mp4)
    except AppError:raise
    except ImportError:raise AppError('VIDEO_CODEC') from None
    except Exception:raise AppError('VIDEO_INVALID') from None


def _normalize(data, folder, mp4):
    import av
    source=folder/'recorded-source.bin';target=folder/'normalized.mp4'
    source.write_bytes(data);started=time.monotonic();guard_memory(video=True)
    incoming=av.open(str(source));outgoing=None
    try:
        if (not incoming.streams.video or incoming.streams.audio or
                not any(x in incoming.format.name.split(',') for x in (('mov','mp4') if mp4 else ('matroska','webm')))):
            raise AppError('VIDEO_INVALID')
        stream=incoming.streams.video[0];stream.thread_count=1
        width,height=stream.width,stream.height
        if min(width,height)<=0 or max(width,height)>LIMITS.video_long_side or width*height>LIMITS.video_pixels:
            raise AppError('VIDEO_LIMITS')
        if stream.metadata.get('rotate','0') not in ('0',''):raise AppError('VIDEO_ROTATION')
        if stream.codec_context.name not in (('h264',) if mp4 else ('vp8','vp9')):raise AppError('VIDEO_CODEC')
        duration=(float(stream.duration*stream.time_base) if stream.duration is not None else
                  incoming.duration/av.time_base if incoming.duration is not None else None)
        if duration is not None and (not math.isfinite(duration) or not 0<duration<=LIMITS.video_seconds+.01):
            raise AppError('VIDEO_LIMITS')
        rate=float(stream.average_rate) if stream.average_rate else 15.
        if not math.isfinite(rate) or not 0<rate<=60:raise AppError('VIDEO_LIMITS')
        if not mp4:
            if width%2 or height%2:raise AppError('VIDEO_LIMITS')
            outgoing=av.open(str(target),'w',format='mp4',options={'movflags':'+faststart'})
            encoded=outgoing.add_stream('libx264',rate=15);encoded.width=width;encoded.height=height
            encoded.pix_fmt='yuv420p';encoded.thread_count=1;encoded.options={'preset':'veryfast','crf':'23'}
            encoded.time_base=Fraction(1,90000)
            encoded.codec_context.time_base=Fraction(1,90000)
            encoded.codec_context.max_b_frames=0
        first=last=None;count=0;last_delta=1/rate
        for frame in quiet_decode(incoming):
            if time.monotonic()-started>min(20,LIMITS.job_seconds):raise AppError('JOB_TIMEOUT')
            count+=1
            if count>LIMITS.video_seconds*60+8:raise AppError('VIDEO_LIMITS')
            if frame.width!=width or frame.height!=height:raise AppError('VIDEO_INVALID')
            if any('DISPLAYMATRIX' in str(x.type).upper() for x in frame.side_data):raise AppError('VIDEO_ROTATION')
            raw=float(frame.time) if frame.time is not None else None
            if raw is None or not math.isfinite(raw):raise AppError('VIDEO_INVALID')
            if first is None:first=raw
            stamp=raw-first
            if stamp<0 or stamp>=LIMITS.video_seconds or (last is not None and stamp<=last):raise AppError('VIDEO_LIMITS')
            if last is not None:last_delta=stamp-last
            last=stamp;guard_memory(video=True)
            if outgoing:
                frame=frame.reformat(width=width,height=height,format='yuv420p')
                frame.pts=round(stamp*90000);frame.time_base=Fraction(1,90000)
                for packet in encoded.encode(frame):outgoing.mux(packet)
                if target.exists() and target.stat().st_size>LIMITS.video_bytes:raise AppError('UPLOAD_TOO_LARGE')
        if not count or last+last_delta>LIMITS.video_seconds+.01:raise AppError('VIDEO_LIMITS')
        if outgoing:
            for packet in encoded.encode():outgoing.mux(packet)
            outgoing.close();outgoing=None
    finally:
        incoming.close()
        if outgoing:outgoing.close()
    if mp4:
        video_metadata(source)  # Same metadata contract as uploaded MP4.
        return data
    if target.stat().st_size>LIMITS.video_bytes:raise AppError('UPLOAD_TOO_LARGE')
    video_metadata(target)
    return target.read_bytes()
