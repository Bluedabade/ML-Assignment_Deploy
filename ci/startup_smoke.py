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
        if app.exception or len(app.title) != 1 or 'SKN-1' not in app.title[0].value:
            raise RuntimeError('INITIAL_UI_RENDER_FAILED')
        if len(app.radio) != 1 or len(app.selectbox) != 1:
            raise RuntimeError('INITIAL_UI_CONTROLS_MISSING')
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
    return {'status': 'STREAMLIT_STARTUP_PASSED', 'initial_ui_rendered': True,
            'localhost_health_passed': True, 'sdk_imported': False, 'model_load_calls': 0,
            'cloud_inference_verified': False}


if __name__ == '__main__':
    try:print(json.dumps(check()))
    except Exception:
        print(json.dumps({'status': 'STREAMLIT_STARTUP_FAILED', 'model_load_calls': 0}))
        raise SystemExit(1)
