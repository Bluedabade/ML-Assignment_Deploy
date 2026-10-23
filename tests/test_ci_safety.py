"""CI gates use dummy data, never credentials, network requests or real models."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ci.audit_source import FILES, ROOT, audit, scan_text, sensitive_file
from ci.safety import assert_no_credentials, external_address, network_audit, forbid_model


class CIGates(unittest.TestCase):
    def test_current_source_manifest_and_allowlist(self):
        self.assertEqual(audit()['publication_files'],len(FILES))

    def test_network_policy_allows_only_loopback(self):
        for address in [('127.0.0.1',8501),('::1',8501),('localhost',8501)]:
            self.assertFalse(external_address(address))
        for address in [('api.roboflow.com',443),('8.8.8.8',443),'/tmp/socket',('192.168.1.1',80)]:
            self.assertTrue(external_address(address))
            with self.assertRaises(RuntimeError):network_audit('socket.connect',(None,address))

    def test_credentials_presence_rejected_without_value_output(self):
        with patch.dict(os.environ,{'ROBOFLOW_API_KEY':'dummy-ci-only'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'^CI_CREDENTIAL_PRESENT$'):assert_no_credentials()
        with patch.dict(os.environ,{},clear=True):assert_no_credentials()

    def test_real_model_loading_forbidden(self):
        with self.assertRaisesRegex(RuntimeError,'^CI_MODEL_LOADING_FORBIDDEN$'):forbid_model()

    def test_secrets_and_media_names_rejected(self):
        for name in ('.env','.env.local','secrets.toml','weights.onnx','blob.bin','photo.JPG','video.mp4'):
            self.assertTrue(sensitive_file(Path(name)))
        self.assertFalse(sensitive_file(Path('skn_app/secrets.py')))
        self.assertFalse(sensitive_file(Path('deployment/secrets.example.toml')))

    def test_placeholder_only_secret_templates(self):
        scan_text('ROBOFLOW_API_KEY="REPLACE_WITH_PRIVATE_KEY"')
        with self.assertRaisesRegex(ValueError,'NON_PLACEHOLDER_KEY_LITERAL'):
            scan_text('ROBOFLOW_API_KEY="dummy-not-a-placeholder"')

    def test_no_hidden_artifact_can_enter_allowlist(self):
        # Test an independent synthetic root, not the actual publication tree.
        with tempfile.TemporaryDirectory(prefix='ci-audit-') as folder:
            root=Path(folder);(root/'unexpected.bin').write_bytes(b'synthetic')
            with self.assertRaises(ValueError):audit(root)

    def test_workflow_yaml_and_security_contract(self):
        import yaml
        data=yaml.load((ROOT/'.github/workflows/linux-build.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertEqual(set(data['on']),{'push','pull_request','workflow_dispatch'})
        self.assertEqual(data['permissions'],{'contents':'read'})
        job=data['jobs']['linux-cpu'];self.assertEqual(job['runs-on'],'ubuntu-22.04')
        steps=job['steps'];actions=[step for step in steps if 'uses' in step]
        self.assertEqual(len(actions),2)
        for action in actions:self.assertRegex(action['uses'],r'^actions/[a-z-]+@[0-9a-f]{40}$')
        self.assertEqual(actions[0]['with']['persist-credentials'],'false')
        self.assertEqual(actions[1]['with']['python-version'],'3.11')
        commands='\n'.join(step.get('run','') for step in steps)
        for expected in ('pip check','ci.check_runtime','ci.run_synthetic','ci.startup_smoke','ci.audit_source --check-scratch'):
            self.assertIn(expected,commands)

    def test_extensionless_scratch_artifact_rejected(self):
        with tempfile.TemporaryDirectory(prefix='ci-scratch-audit-') as folder:
            root=Path(folder);scratch=root/'.ci_tmp';scratch.mkdir()
            (scratch/'extensionless-blob').write_bytes(b'synthetic-not-a-model')
            with self.assertRaisesRegex(ValueError,'^SCRATCH_PRIVATE_ARTIFACT_FOUND$'):
                audit(root,check_scratch=True)


if __name__=='__main__':unittest.main()
