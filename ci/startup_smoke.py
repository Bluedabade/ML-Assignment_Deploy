"""Render the initial UI and test a real localhost server without loading models."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from unittest.mock import patch
from .safety import install_guard, forbid_model


ROOT = Path(__file__).resolve().parents[1]


def check_camera_ui():
    """Native empty camera plus injected JPEG for integration, never a hardware claim."""
    import io
    from types import SimpleNamespace
    from PIL import Image
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from skn_app import ui
    from skn_app.media import process_image
    from skn_app.presentation import CACHE_SLOT
    source="from skn_app.ui import detection\ndetection('image','local')"
    with patch.object(ui,'service',side_effect=forbid_model) as service:
        native=AppTest.from_string(source).run()
        if native.exception or len(native.get('file_uploader'))!=1 or native.get('camera_input'):
            raise RuntimeError('IMAGE_SOURCE_DEFAULT_FAILED')
        native.segmented_control[0].set_value('camera').run()
        if native.exception or len(native.get('camera_input'))!=1 or native.get('file_uploader'):
            raise RuntimeError('CAMERA_NATIVE_INPUT_MISSING')
        native.segmented_control[0].set_value('upload').run()
        if native.exception or native.get('camera_input') or len(native.get('file_uploader'))!=1:
            raise RuntimeError('CAMERA_UPLOAD_SWITCH_FAILED')
        service.assert_not_called()
    output=io.BytesIO();Image.new('RGB',(1280,720),'#aabbcc').save(output,format='JPEG')
    data=output.getvalue();calls=[];predict_calls=[];camera_keys=[]
    class Runtime:
        def load(self):pass
        def predict_candidates(self,image):
            predict_calls.append(1)
            return [dict(class_name='acne',confidence=.8,x1=20.,y1=30.,x2=80.,y2=90.)],.01
    def process(payload,kind,profile,progress):
        if payload!=data or kind!='image' or profile!='Balanced':raise RuntimeError('CAMERA_SHARED_PAYLOAD_CHANGED')
        calls.append(1)
        return process_image(payload,Runtime(),profile)
    def camera(*args,**kwargs):
        camera_keys.append(kwargs['key'])
        if kwargs.get('resolution')!='720p':raise RuntimeError('CAMERA_RESOLUTION_CHANGED')
        return SimpleNamespace(size=len(data),getvalue=lambda:data) if kwargs['key']=='camera-image-1' else None
    with patch.object(st,'camera_input',side_effect=camera),patch.object(ui,'service',return_value=SimpleNamespace(process_media=process)) as service,patch('skn_app.media.guard_memory'):
        flow=AppTest.from_string(source).run()
        flow.segmented_control[0].set_value('camera').run()
        if flow.exception or calls:raise RuntimeError('CAMERA_AUTOMATIC_INFERENCE')
        next(b for b in flow.button if b.label=='เริ่มตรวจจับปัญหาผิว').click().run()
        if flow.exception or len(calls)!=1 or len(predict_calls)!=1 or len(flow.metric)!=4:
            raise RuntimeError('CAMERA_PROCESS_FAILED')
        flow.multiselect[0].set_value(['wrinkle']).run()
        flow.slider[0].set_value(90).run()
        flow.slider[1].set_value(10).run()
        flow.selectbox[1].set_value('none').run()
        flow.radio[0].set_value('ภาพต้นฉบับ').run()
        if flow.exception or len(calls)!=1 or flow.multiselect[0].value!=['wrinkle'] or flow.metric[0].value!='0':
            raise RuntimeError('CAMERA_CACHED_CONTROLS_FAILED')
        next(b for b in flow.button if b.label=='ถ่ายภาพใหม่').click().run()
        if flow.exception or CACHE_SLOT in flow.session_state or 'care-image' in flow.session_state or flow.metric:
            raise RuntimeError('CAMERA_RETAKE_STALE_RESULT')
        if len(calls)!=1 or camera_keys[-1]=='camera-image-1':raise RuntimeError('CAMERA_RETAKE_GENERATION_FAILED')
        next(b for b in flow.button if b.label=='เลือกภาพจากอุปกรณ์แทน').click().run()
        if flow.exception or flow.session_state['image_input_source']!='upload' or not flow.get('file_uploader'):
            raise RuntimeError('CAMERA_PERMISSION_FALLBACK_FAILED')
        service.assert_called_once()
        # Source switch must invalidate even when the results early-return is active.
        second=AppTest.from_string(source).run()
        second.segmented_control[0].set_value('camera').run()
        next(b for b in second.button if b.label=='เริ่มตรวจจับปัญหาผิว').click().run()
        if second.exception or CACHE_SLOT not in second.session_state:raise RuntimeError('CAMERA_SECOND_SESSION_FAILED')
        second.multiselect[0].set_value(['wrinkle']).run()
        second.segmented_control[0].set_value('upload').run()
        if second.exception or CACHE_SLOT in second.session_state or 'care-image' in second.session_state or second.metric:
            raise RuntimeError('CAMERA_SOURCE_SWITCH_STALE_RESULT')
        second.segmented_control[0].set_value('camera').run()
        if second.exception or second.metric or any(b.label=='เริ่มตรวจจับปัญหาผิว' for b in second.button):
            raise RuntimeError('CAMERA_SOURCE_SWITCH_REUSED_PHOTO')
        if len(calls)!=2 or len(predict_calls)!=2:raise RuntimeError('CAMERA_SOURCE_SWITCH_INFERENCE')
    return True


def check():
    install_guard()
    scratch = ROOT/'.ci_tmp';scratch.mkdir(exist_ok=True);tempfile.tempdir = str(scratch)
    from streamlit.testing.v1 import AppTest
    from skn_app import runtime
    with patch.object(runtime, 'load_official', side_effect=forbid_model) as loader:
        app = AppTest.from_file(str(ROOT/'deployment/streamlit_app.py'), default_timeout=20).run()
        if app.exception or len(app.title) != 1 or 'ระบบตรวจจับปัญหาผิว' not in app.title[0].value:
            raise RuntimeError('INITIAL_UI_RENDER_FAILED')
        if len(app.radio) != 1 or len(app.radio[0].options) != 6:
            raise RuntimeError('INITIAL_UI_CONTROLS_MISSING')
        from skn_app.ui import PAGES, THAI, PROFILE_LABELS, display_rows
        for theme in ('dark', 'light', 'system'):
            app.session_state['appearance'] = theme
            app.run()
            if app.exception:raise RuntimeError('THEME_SWITCH_FAILED')
        for page in PAGES:
            app.radio[0].set_value(page).run()
            if app.exception:raise RuntimeError('NAVIGATION_RENDER_FAILED')
        app.radio[0].set_value(PAGES[0]).run()
        next(button for button in app.button if button.label == 'เริ่มตรวจจับจากภาพ').click().run()
        if app.session_state['navigation'] != PAGES[1]:raise RuntimeError('HERO_NAVIGATION_FAILED')
        # Image display controls live in the result fragment only after inference.
        if len(app.selectbox) != 0:raise RuntimeError('IMAGE_CONTROLS_BEFORE_INFERENCE')
        app.radio[0].set_value(PAGES[2]).run()
        if app.selectbox[0].options != list(PROFILE_LABELS.values()):raise RuntimeError('THAI_PROFILE_LABELS_FAILED')
        rows = [{'class_name':'acne','confidence':.8,'x1':1}]
        translated = display_rows(rows)
        if translated[0]['ประเภท'] != THAI['acne'] or rows[0]['class_name'] != 'acne':
            raise RuntimeError('DISPLAY_SCHEMA_MUTATION')
        # Presentation-only fixture: no predictions are obtained from a real model.
        fixture = '''
import io
from PIL import Image
from skn_app.ui import results_view
from skn_app.media import csv_bytes
output=io.BytesIO();Image.new('RGB',(64,48),'teal').save(output,format='PNG')
rows=[dict(class_name='acne',confidence=.8,x1=1.,y1=2.,x2=10.,y2=12.)]
result=dict(counts=dict(acne=1,wrinkle=0,dark_spot=0,enlarged_pore=0),
 predictions=rows,image_bytes=output.getvalue(),csv_bytes=csv_bytes(rows),inference_seconds=.01)
results_view(result,'image')
'''
        rendered = AppTest.from_string(fixture).run()
        if rendered.exception or len(rendered.metric) != 4 or len(rendered.dataframe) != 1:
            raise RuntimeError('SYNTHETIC_RESULT_RENDER_FAILED')
        if rendered.dataframe[0].value.iloc[0]['ประเภท'] != THAI['acne']:
            raise RuntimeError('RESULT_TRANSLATION_FAILED')
        if len(rendered.get('download_button')) != 2:
            raise RuntimeError('RESULT_DOWNLOAD_CONTROLS_MISSING')
        rendered.button[0].click().run()
        if rendered.session_state['upload_generation'] != 1:
            raise RuntimeError('CLEAR_SESSION_FAILED')
        pore_fixture = '''
import io
from PIL import Image
from skn_app.ui import results_view
from skn_app.media import csv_bytes
output=io.BytesIO();Image.new('RGB',(64,48),'teal').save(output,format='PNG')
rows=[dict(class_name='enlarged_pore',confidence=.35,x1=20.,y1=20.,x2=40.,y2=40.)]
result=dict(counts=dict(acne=0,wrinkle=0,dark_spot=0,enlarged_pore=1),
 predictions=rows,image_bytes=output.getvalue(),csv_bytes=csv_bytes(rows),inference_seconds=.01)
results_view(result,'image')
'''
        pore_view = AppTest.from_string(pore_fixture).run()
        if pore_view.exception or pore_view.metric[3].label != THAI['enlarged_pore'] or pore_view.metric[3].value != '1':
            raise RuntimeError('PORE_METRIC_RENDER_FAILED')
        if pore_view.dataframe[0].value.iloc[0]['ประเภท'] != THAI['enlarged_pore']:
            raise RuntimeError('PORE_TABLE_RENDER_FAILED')
        if pore_view.dataframe[0].value.iloc[0]['ความเชื่อมั่น'] != '35.0%':
            raise RuntimeError('PORE_CONFIDENCE_RENDER_FAILED')
        if not any('คล้ายรูขุมขนกว้าง' in node.label for node in pore_view.expander):
            raise RuntimeError('PORE_GUIDANCE_RENDER_FAILED')
        from skn_app.skincare_guidance import (MEDICAL_DISCLAIMER, NUTRITION_DISCLAIMER,
            NO_DETECTION_MESSAGE, SKINCARE_GUIDANCE)
        from skn_app import ui
        with patch.object(ui, 'service', side_effect=forbid_model) as adapter:
            for kind in ('image','video'):
                fixture = ('from skn_app.ui import skincare_guidance_view\n'
                    f"skincare_guidance_view({{}},input_kind={kind!r},identity='fixture-file')")
                concern_view = AppTest.from_string(fixture).run()
                if concern_view.exception or concern_view.multiselect[0].value:
                    raise RuntimeError('CONCERN_DEFAULT_NOT_EMPTY')
                concern_view.multiselect[0].set_value(['acne','wrinkle','other_unsure']).run()
                text='\n'.join(str(n.value) for n in concern_view.markdown)
                if concern_view.exception or 'คุณเลือกศึกษาข้อมูลเกี่ยวกับสิว' not in text:
                    raise RuntimeError('CONCERN_IMAGE_VIDEO_FAILED')
                if any('ระบบ AI พบลักษณะภาพ' in str(n.value) for n in concern_view.markdown):
                    raise RuntimeError('USER_CONCERN_CLAIMS_AI_DETECTION')
                concern_view.multiselect[0].set_value([]).run()
                if concern_view.exception:raise RuntimeError('CONCERN_DESELECT_FAILED')
            for counts, showcase in [({'acne':1},False), ({'wrinkle':1},False),
                    ({'dark_spot':1},False), ({'enlarged_pore':1},False),
                    (dict.fromkeys(THAI,1),False), ({},False), ({'unknown':1},False), ({},True)]:
                code = ('from skn_app.ui import skincare_guidance_view\n'
                        f'skincare_guidance_view({counts!r}, showcase={showcase!r})')
                view = AppTest.from_string(code).run()
                if view.exception:raise RuntimeError('GUIDANCE_RENDER_FAILED')
                text = '\n'.join(str(node.value) for kind in ('info','caption','markdown','subheader') for node in view.get(kind))
                if MEDICAL_DISCLAIMER not in text or NUTRITION_DISCLAIMER not in text:
                    raise RuntimeError('GUIDANCE_DISCLAIMER_MISSING')
                if not counts and not showcase and NO_DETECTION_MESSAGE not in text:
                    raise RuntimeError('GUIDANCE_EMPTY_STATE_FAILED')
                if showcase:
                    if 'ข้อมูลสาธิตเท่านั้น' not in text or SKINCARE_GUIDANCE['acne']['description'] in text:
                        raise RuntimeError('SHOWCASE_CLAIMS_REAL_DETECTION')
            adapter.assert_not_called()
        interactive_fixture = '''
import io,time
from PIL import Image
import streamlit as st
from skn_app.ui import interactive_image_results
from skn_app.presentation import make_image_cache,CACHE_SLOT
output=io.BytesIO();Image.new('RGB',(120,80),'white').save(output,format='PNG')
data=output.getvalue()
rows=[dict(class_name='enlarged_pore',confidence=c,x1=x,y1=25.,x2=x+20.,y2=50.) for c,x in ((.15,10.),(.35,60.))]
if CACHE_SLOT not in st.session_state:
 st.session_state[CACHE_SLOT]=make_image_cache(data,dict(candidates=rows,inference_seconds=.01,model_loads=0),time.time())
interactive_image_results(st.session_state[CACHE_SLOT]['key'])
'''
        with patch.object(ui, 'service', side_effect=forbid_model) as adapter:
            interactive = AppTest.from_string(interactive_fixture).run()
            if interactive.exception or interactive.metric[3].value != '1':
                raise RuntimeError('INTERACTIVE_BASELINE_FAILED')
            interactive.multiselect[0].set_value(['wrinkle','enlarged_pore']).run()
            if interactive.exception or len([e for e in interactive.expander if 'คล้ายรูขุมขนกว้าง' in e.label]) != 1:
                raise RuntimeError('CONCERN_DEDUP_FAILED')
            concern_key = interactive.multiselect[0].key
            if interactive.slider[0].value != 25:raise RuntimeError('DEFAULT_SLIDER_MISSING')
            if not any(e.label=='ตั้งค่าขั้นสูง' for e in interactive.expander):raise RuntimeError('ADVANCED_MISSING')
            interactive.radio[0].set_value('ภาพต้นฉบับ').run()
            if interactive.exception:raise RuntimeError('ORIGINAL_SWITCH_FAILED')
            interactive.radio[0].set_value('ภาพผลตรวจจับ').run()
            interactive.slider[0].set_value(10).run()
            if interactive.exception or interactive.metric[3].value != '2' or not interactive.warning:
                raise RuntimeError('INTERACTIVE_LOW_THRESHOLD_FAILED')
            interactive.slider[0].set_value(90).run()
            if interactive.exception or interactive.metric[3].value != '0':
                raise RuntimeError('INTERACTIVE_HIGH_THRESHOLD_FAILED')
            if interactive.multiselect[0].value != ['wrinkle','enlarged_pore']:
                raise RuntimeError('CONCERNS_LOST_ON_THRESHOLD_CHANGE')
            selected_text = '\n'.join(str(n.value) for n in interactive.markdown)
            if 'คุณเลือกศึกษาข้อมูลเกี่ยวกับริ้วรอย' not in selected_text:
                raise RuntimeError('USER_CONTEXT_MISSING')
            interactive.slider[1].set_value(10).run()
            interactive.selectbox[1].set_value('none').run()
            interactive.selectbox[0].set_value('Precision-focused').run()
            if interactive.exception or interactive.metric[3].value != '1':
                raise RuntimeError('INTERACTIVE_PROFILE_FAILED')
            next(b for b in interactive.button if b.label == 'รีเซ็ตการแสดงผล').click().run()
            if interactive.exception or interactive.selectbox[0].value != 'Balanced':
                raise RuntimeError('INTERACTIVE_RESET_FAILED')
            adapter.assert_not_called()
        check_camera_ui()
        from skn_app import video_recorder
        video_source="from skn_app.ui import detection\ndetection('video','cloud')"
        with patch.object(ui,'service',side_effect=forbid_model) as no_service:
            record_view=AppTest.from_string(video_source).run()
            record_view.segmented_control[0].set_value('record').run()
            if record_view.exception or record_view.get('file_uploader'):
                raise RuntimeError('RECORDER_COMPONENT_RENDER_FAILED')
            no_service.assert_not_called()
        clip=dict(b64='AAAAGGZ0eXBpc29t',mime='video/mp4',seconds=1.)
        payload=video_recorder.decode_clip(clip)[0]
        def recorded(key):return (payload,'video/mp4') if key=='video-recorder-1' else None
        with patch.object(video_recorder,'recorder',side_effect=recorded),patch.object(ui,'service',side_effect=forbid_model) as no_service:
            gate=AppTest.from_string(video_source).run()
            gate.segmented_control[0].set_value('record').run()
            if gate.exception or not next(b for b in gate.button if b.label=='เริ่มวิเคราะห์วิดีโอ').disabled:
                raise RuntimeError('RECORDER_CLOUD_GATE_REMOVED')
            next(b for b in gate.button if b.label=='ถ่ายวิดีโอใหม่').click().run()
            if gate.exception or any(b.label=='เริ่มวิเคราะห์วิดีโอ' for b in gate.button):raise RuntimeError('RECORDER_RETAKE_STALE_MEDIA')
            gate.segmented_control[0].set_value('upload').run()
            if gate.exception or not gate.get('file_uploader'):raise RuntimeError('RECORDER_UPLOAD_FALLBACK_FAILED')
            no_service.assert_not_called()
        from types import SimpleNamespace
        video_calls=[]
        def video_job(data,kind,profile,progress):
            if data!=payload or kind!='recorded_video':raise RuntimeError('RECORDED_VIDEO_ROUTING_CHANGED')
            video_calls.append(1)
            return dict(video_bytes=payload,csv_bytes=b'timestamp_seconds,class_name,confidence,x1,y1,x2,y2\n',
                counts=dict.fromkeys(THAI,0),predictions=[],frames=[],inference_seconds=0.)
        with patch.object(video_recorder,'recorder',side_effect=recorded),patch.object(ui,'service',return_value=SimpleNamespace(process_media=video_job)):
            allowed=AppTest.from_string("import streamlit as st\nst.session_state['image_verified']=True\n"+video_source).run()
            allowed.segmented_control[0].set_value('record').run()
            if video_calls:raise RuntimeError('RECORDER_AUTO_PROCESSING')
            next(b for b in allowed.button if b.label=='เริ่มวิเคราะห์วิดีโอ').click().run()
            if allowed.exception or len(video_calls)!=1 or len(allowed.metric)!=4:raise RuntimeError('RECORDED_VIDEO_PROCESS_BUTTON_FAILED')
            allowed.selectbox[0].set_value('Precision-focused').run()
            if len(video_calls)!=1:raise RuntimeError('RECORDER_DUPLICATE_JOB')
        loader.assert_not_called()
    if any(n == 'inference_models' or n.startswith('inference_models.') for n in sys.modules):
        raise RuntimeError('SDK_IMPORTED_DURING_INITIAL_UI')
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0));port = endpoint.getsockname()[1]
    code = ('from ci.safety import install_guard,forbid_model; install_guard(); '
            'from skn_app import runtime; runtime.load_official=forbid_model; '
            'from streamlit.web import cli; cli.main()')
    command = [sys.executable, '-B', '-c', code, 'run', 'deployment/streamlit_app.py',
               '--server.address=127.0.0.1', f'--server.port={port}', '--server.headless=true',
               '--browser.gatherUsageStats=false']
    environment = dict(os.environ, TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
    process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic()+25
        while True:
            if process.poll() is not None:
                raise RuntimeError('STREAMLIT_EXITED')
            try:
                with opener.open(f'http://127.0.0.1:{port}/_stcore/health', timeout=1) as response:
                    if response.status == 200 and response.read() == b'ok':break
            except OSError:
                if time.monotonic() > deadline:raise RuntimeError('STREAMLIT_STARTUP_TIMEOUT') from None
                time.sleep(.2)
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    return {'status': 'STREAMLIT_STARTUP_PASSED', 'initial_ui_rendered': True, 'thai_pages_checked': 6, 'hero_navigation': True,
            'localhost_health_passed': True, 'sdk_imported': False, 'model_load_calls': 0,
            'guidance_cases_checked': 8, 'enlarged_pore_result_checked': True,
            'interactive_controls_verified': True, 'camera_synthetic_flow_verified': True,
            'video_recorder_synthetic_ui_verified': True,
            'camera_hardware_verified': False, 'cloud_inference_verified': False}


if __name__ == '__main__':
    try:print(json.dumps(check()))
    except Exception:
        print(json.dumps({'status': 'STREAMLIT_STARTUP_FAILED', 'model_load_calls': 0}))
        raise SystemExit(1)
