"""Bounded browser-recorder transport. No SDK, camera, or model on the server."""
import base64
import binascii
import math
from pathlib import Path
from .config import LIMITS
from .errors import AppError

MIMES = ('video/mp4', 'video/webm')


def decode_clip(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'b64','mime','seconds'}:
        raise AppError('INPUT_INVALID')
    text,mime,seconds=value['b64'],value['mime'],value['seconds']
    if (mime not in MIMES or type(seconds) not in (int,float) or not math.isfinite(seconds)
            or not 0<seconds<=LIMITS.video_seconds):raise AppError('VIDEO_LIMITS')
    if not isinstance(text,str) or len(text)>4*((LIMITS.video_bytes+2)//3):
        raise AppError('UPLOAD_TOO_LARGE')
    try:data=base64.b64decode(text,validate=True)
    except (ValueError,binascii.Error):raise AppError('VIDEO_INVALID') from None
    if not data or len(data)>LIMITS.video_bytes:raise AppError('UPLOAD_TOO_LARGE')
    if ((mime=='video/mp4' and data[4:8]!=b'ftyp') or
            (mime=='video/webm' and not data.startswith(b'\x1aE\xdf\xa3'))):raise AppError('VIDEO_INVALID')
    return data,mime


def recorder(key):
    import streamlit.components.v2 as v2
    javascript=Path(__file__).with_name('recorder.js').read_text(encoding='utf-8')
    component=v2.component('skn_browser_video_recorder',js=javascript)
    result=component(key=key,on_clip_change=lambda:None,
        data={'maxBytes':LIMITS.video_bytes,'maxSeconds':LIMITS.video_seconds})
    return decode_clip(result.get('clip'))


class RecordedClip:
    def __init__(self,data,mime):self.data,self.mime,self.size=data,mime,len(data)
    def getvalue(self):return self.data
