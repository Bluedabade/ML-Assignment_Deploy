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
        if len(app.selectbox) != 1:raise RuntimeError('PROFILE_CONTROL_MISSING')
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
            'cloud_inference_verified': False}


if __name__ == '__main__':
    try:print(json.dumps(check()))
    except Exception:
        print(json.dumps({'status': 'STREAMLIT_STARTUP_FAILED', 'model_load_calls': 0}))
        raise SystemExit(1)
