"""Exact publication allowlist, fingerprints, source checks and no-media/cache artifact gate."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = frozenset('''
.gitignore
.github/workflows/linux-build.yml
.streamlit/config.toml
DEPLOY_STREAMLIT_CLOUD.md
README.md
SOURCE_PROVENANCE.json
bundle_manifest.json
deployment/.env.example
deployment/dependency_audit.py
deployment/requirements.txt
deployment/secrets.example.toml
deployment/streamlit_app.py
packages.txt
streamlit_app.py
skn_app/__init__.py
skn_app/cloud_adapter.py
skn_app/config.py
skn_app/errors.py
skn_app/local_adapter.py
skn_app/media.py
skn_app/resources.py
skn_app/runtime.py
skn_app/secrets.py
skn_app/ui.py
skn_app/skincare_guidance.py
skn_app/worker.py
ci/__init__.py
ci/audit_source.py
ci/check_runtime.py
ci/run_synthetic.py
ci/safety.py
ci/startup_smoke.py
tests/test_skn_app.py
tests/test_ci_safety.py
tests/test_skincare_guidance.py
docs/LICENSING.md
docs/LICENSE_PERMISSION_REQUEST.md
'''.split())
IGNORED_LOCAL = {'reports', '.ci_tmp', '.git'}
FORBIDDEN_DIRS = {'datasets', 'runs', 'results', 'model_cache', 'models-cache', 'shared-blobs',
                  'auto-resolution-cache', 'uploads', 'uploaded_media', '.venv', 'venv'}
FORBIDDEN_SUFFIXES = {'.onnx', '.pt', '.pth', '.ckpt', '.safetensors', '.bin', '.jpg', '.jpeg',
                      '.png', '.gif', '.bmp', '.webp', '.mp4', '.mov', '.avi', '.mkv', '.pem', '.key'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sensitive_file(path):
    return (path.name in {'.env', 'secrets.toml'} or
            (path.name.startswith('.env.') and path.name != '.env.example') or
            path.suffix.lower() in FORBIDDEN_SUFFIXES)


def scan_text(text, allow_dummy=False):
    # Specific credential signatures; SHA256 provenance/model identities are not secrets.
    patterns = [r'\bgh[pousr]_[A-Za-z0-9]{20,}', r'\bgithub_pat_[A-Za-z0-9_]{20,}',
                r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                r'(?i)\broboflow_api_key\s*[=:]\s*["\x27]?([^\s"\x27#]+)']
    for pattern in patterns[:3]:
        if re.search(pattern, text):raise ValueError('CREDENTIAL_SIGNATURE_FOUND')
    for match in re.finditer(patterns[3], text):
        value = match.group(1)
        if allow_dummy and value.lower().startswith('dummy-'):
            continue  # Only the two exact synthetic test sources may contain dummy fixtures.
        if value.lower() not in {'replace_with_private_key', 'replace_with_your_private_key'}:
            raise ValueError('NON_PLACEHOLDER_KEY_LITERAL')


def audit(root=ROOT, check_scratch=False):
    root = Path(root).resolve()
    actual = set()
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if rel.parts[0] in IGNORED_LOCAL:
            if path.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
            if check_scratch and rel.parts[0] == '.ci_tmp':
                # Reject every remaining file, including extensionless shared blobs.
                if path.is_file() or (path.is_dir() and path.name in FORBIDDEN_DIRS):
                    raise ValueError('SCRATCH_PRIVATE_ARTIFACT_FOUND')
            continue
        if path.is_symlink():raise ValueError('SYMLINK_FORBIDDEN')
        if path.is_file():
            name = rel.as_posix();actual.add(name)
            if name not in FILES or sensitive_file(path):raise ValueError('NON_ALLOWLISTED_FILE')
            text = path.read_text(encoding='utf-8')
            scan_text(text, allow_dummy=name in {'tests/test_skn_app.py', 'tests/test_ci_safety.py'})
            if path.suffix == '.py':ast.parse(text, filename=name)
    if actual != FILES:raise ValueError('ALLOWLIST_INCOMPLETE')
    manifest = json.loads((root/'bundle_manifest.json').read_text())
    if set(manifest) != FILES-{'bundle_manifest.json'}:raise ValueError('MANIFEST_MEMBERSHIP_MISMATCH')
    if any(sha(root/name) != fingerprint for name, fingerprint in manifest.items()):
        raise ValueError('SOURCE_HASH_CHANGED')
    workflow = (root/'.github/workflows/linux-build.yml').read_text()
    if any(word in workflow for word in ('secrets.', 'pull_request_target', 'upload-artifact@', 'actions/cache@')):
        raise ValueError('UNSAFE_WORKFLOW_FEATURE')
    if not re.search(r'contents:\s*read\b', workflow):raise ValueError('WORKFLOW_PERMISSIONS')
    if not (root/'deployment/requirements.txt').is_file():raise ValueError('DEPENDENCY_DISCOVERY')
    return {'status': 'SOURCE_ONLY_AUDIT_PASSED', 'publication_files': len(FILES),
            'hashes_checked': len(manifest), 'secret_signature_hits': 0,
            'model_or_media_artifacts': 0, 'symlinks': 0,
            'local_reports_publishable': False, 'scratch_checked': check_scratch}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-scratch', action='store_true')
    args = parser.parse_args()
    try:print(json.dumps(audit(check_scratch=args.check_scratch)))
    except Exception:
        print(json.dumps({'status': 'SOURCE_ONLY_AUDIT_FAILED'}));raise SystemExit(1)
