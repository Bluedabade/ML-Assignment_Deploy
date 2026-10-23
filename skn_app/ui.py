"""One UI shared by the original local entrypoint and the cloud dependency wrapper."""
import hashlib
import time
import streamlit as st
from .config import CLASSES, LIMITS, PROFILES, mode
from .errors import AppError, MESSAGES
from .media import decode_image


@st.cache_resource(max_entries=1, show_spinner=False)
def service(environment):
    if environment == 'local':
        from .local_adapter import LocalAdapter
        return LocalAdapter()
    from .cloud_adapter import CloudAdapter
    return CloudAdapter(lambda name: st.secrets[name])


def main():
    st.set_page_config(page_title='SKN-1 Skin Detection', page_icon='🔎', layout='wide')
    environment = mode()
    st.title('Skin Problem Detection · SKN-1')
    st.caption('ระบบช่วยตรวจจับจากภาพสำหรับโครงงาน Machine Learning ไม่ใช่การวินิจฉัยทางการแพทย์')
    st.info('ไม่พบ Detection ไม่ได้หมายความว่าผิวปกติ ระบบตรวจเฉพาะ acne, wrinkle, dark_spot และ enlarged_pore')
    with st.sidebar:
        st.header('การตรวจจับ')
        profile = st.selectbox('Confidence profile', list(PROFILES))
        st.caption('Balanced ใช้ 0.25 ทุกคลาส ส่วน Precision-focused ลดกล่อง Confidence ต่ำและอาจตรวจพบริ้วรอยน้อยลง')
        st.write('Full image · ONNX CPU · SKN-1')
        st.caption('รูปและวิดีโอประมวลผลใน Runtime ของแอป ไม่ส่ง Media ไป Remote inference API')
        if st.button('ล้างไฟล์และผลลัพธ์ใน Session'):
            for key in ('result', 'signature', 'result_time', 'image_verified'):st.session_state.pop(key, None)
            st.session_state['upload_generation'] = st.session_state.get('upload_generation', 0)+1
        st.markdown('[Model: SKN](https://universe.roboflow.com/skn-f1vaw/skn-1) · [License information](https://github.com/Deci-AI/super-gradients/blob/master/LICENSE.YOLONAS.md)')
    if time.time()-st.session_state.get('result_time', 0) > LIMITS.result_ttl_seconds:
        st.session_state.pop('result', None);st.session_state.pop('signature', None)
    kind = st.radio('ชนิดไฟล์', ['Image', 'Video'], horizontal=True).lower()
    st.caption('JPG/JPEG/PNG · ไม่เกิน 5 MiB และ 4 megapixels' if kind == 'image' else
        'MP4 · ไม่เกิน 20 MiB / 12 วินาที / 1280 พิกเซลด้านยาว · ตรวจตัวอย่าง 1 เฟรมต่อวินาที ไม่ใช่ Real-time')
    uploaded = st.file_uploader('อัปโหลดไฟล์', type=['jpg', 'jpeg', 'png'] if kind == 'image' else ['mp4'],
        key=f"upload-{kind}-{st.session_state.get('upload_generation',0)}")
    if uploaded is None:
        st.caption('ใช้เฉพาะภาพหรือวิดีโอที่คุณมีสิทธิ์และได้รับความยินยอมให้นำมาทดลอง');return
    if uploaded.size > (LIMITS.image_bytes if kind == 'image' else LIMITS.video_bytes):
        st.error(MESSAGES['UPLOAD_TOO_LARGE']);return
    data = uploaded.getvalue();signature = (kind, hashlib.sha256(data).hexdigest(), profile)
    if st.session_state.get('signature') != signature:st.session_state.pop('result', None)
    if kind == 'image':
        try:st.image(decode_image(data), caption='ภาพต้นฉบับ', width='stretch')
        except AppError as error:st.error(MESSAGES[error.code]);return
    blocked = environment == 'cloud' and kind == 'video' and not st.session_state.get('image_verified')
    if blocked:st.warning(MESSAGES['VIDEO_IMAGE_FIRST'])
    if st.button('ตรวจจับ', type='primary', disabled=blocked):
        st.session_state.pop('result', None);st.session_state.pop('signature', None)
        progress = st.progress(0., text='เตรียม Runtime และตรวจไฟล์…')
        try:
            with st.spinner('กำลังประมวลผล อาจใช้เวลาสำหรับการโหลดโมเดลครั้งแรก…'):
                result = service(environment).process_media(data, kind, profile,
                    lambda done, total: progress.progress(min(1., done/max(total,1)), text=f'ประมวลผล {done}/{total} เฟรมตัวอย่าง'))
            st.session_state.update(result=result, signature=signature, result_time=time.time())
            if kind == 'image':st.session_state['image_verified'] = True
            progress.progress(1., text='ประมวลผลสำเร็จ')
        except AppError as error:progress.empty();st.error(MESSAGES[error.code])
        except Exception:progress.empty();st.error(MESSAGES['INFERENCE_FAILED'])
    result = st.session_state.get('result') if st.session_state.get('signature') == signature else None
    if result is None:return
    st.subheader('ผลตรวจจับ')
    for column, name in zip(st.columns(4), CLASSES):column.metric(name, result['counts'][name])
    if not any(result['counts'].values()):st.info('ไม่พบ Target เหนือ Confidence ที่เลือก ผลนี้ไม่ใช่การยืนยันว่าผิวปกติ')
    if kind == 'image':
        st.image(result['image_bytes'], caption='ภาพพร้อม Bounding boxes', width='stretch')
        st.download_button('ดาวน์โหลดภาพ Annotated', result['image_bytes'], 'skn_annotated.png', 'image/png')
    else:
        st.video(result['video_bytes'], format='video/mp4')
        st.caption('วิดีโอนี้แสดงเฉพาะเฟรมตัวอย่าง 1 FPS พร้อมเวลาเดิม ไม่มีเสียง และไม่ได้ตรวจทุกเฟรม')
        st.dataframe(result['frames'], hide_index=True)
        st.download_button('ดาวน์โหลดวิดีโอเฟรมตัวอย่าง', result['video_bytes'], 'skn_sampled.mp4', 'video/mp4')
    st.dataframe(result['predictions'], hide_index=True)
    st.download_button('ดาวน์โหลด CSV', result['csv_bytes'], 'skn_detections.csv', 'text/csv')
    st.caption(f"Inference รวม {result['inference_seconds']:.2f} วินาที · {result['backend']}")
