"""Environment > Streamlit Secrets (cloud) or project dotenv (local). No secret output."""
import contextlib
import logging
import os

from .config import ROOT
from .errors import AppError


def authentication(mode, secrets_reader=None):
    name = 'ROBOFLOW_API_KEY'
    if name in os.environ:
        value = os.environ[name]  # Explicit empty values also take precedence.
    elif mode == 'cloud':
        try:
            value = secrets_reader(name) if secrets_reader else None
        except Exception:
            value = None
    else:
        value = None
        logger = logging.getLogger('dotenv.main'); old = logger.disabled
        try:
            logger.disabled = True
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                from dotenv import dotenv_values
                value = dotenv_values(ROOT/'.env', interpolate=False, verbose=False).get(name)
        except Exception:
            value = None
        finally:
            logger.disabled = old
    if not isinstance(value, str) or not value.strip():
        raise AppError('AUTH_MISSING')
    return value
