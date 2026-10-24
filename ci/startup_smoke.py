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
            interactive.slider[1].set_value(10).run()
            interactive.selectbox[1].set_value('none').run()
            interactive.selectbox[0].set_value('Precision-focused').run()
            if interactive.exception or interactive.metric[3].value != '1':
                raise RuntimeError('INTERACTIVE_PROFILE_FAILED')
            next(b for b in interactive.button if b.label == 'รีเซ็ตการแสดงผล').click().run()
            if interactive.exception or interactive.selectbox[0].value != 'Balanced':
                raise RuntimeError('INTERACTIVE_RESET_FAILED')
            adapter.assert_not_called()
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
            'interactive_controls_verified': True, 'cloud_inference_verified': False}


if __name__ == '__main__':
    try:print(json.dumps(check()))
    except Exception:
        print(json.dumps({'status': 'STREAMLIT_STARTUP_FAILED', 'model_load_calls': 0}))
        raise SystemExit(1)
