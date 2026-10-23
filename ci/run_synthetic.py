"""Run only synthetic fixtures with Internet blocked and the real SDK import disabled."""
import importlib.abc
from pathlib import Path
import sys
import tempfile
import unittest
from .safety import install_guard


class BlockSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'inference_models' or fullname.startswith('inference_models.'):
            raise ImportError('CI_REAL_SDK_IMPORT_FORBIDDEN_IN_SYNTHETIC_TESTS')


def main():
    install_guard()
    sys.meta_path.insert(0, BlockSDK())
    scratch = Path(__file__).resolve().parents[1]/'.ci_tmp'
    scratch.mkdir(exist_ok=True)
    tempfile.tempdir = str(scratch)
    suite = unittest.defaultTestLoader.discover('tests', pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
