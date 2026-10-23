"""Fail closed on real credentials, external network calls, and model loading in tests."""
import ipaddress
import os
import sys


def assert_no_credentials():
    # Check presence only. Never read or print a credential value.
    if 'ROBOFLOW_API_KEY' in os.environ:
        raise RuntimeError('CI_CREDENTIAL_PRESENT')


def external_address(address):
    if not isinstance(address, tuple) or not address:
        return True
    host = address[0]
    if host == 'localhost':
        return False
    try:
        return not ipaddress.ip_address(host).is_loopback
    except ValueError:
        return True


def network_audit(event, args):
    if event == 'socket.connect' and external_address(args[1]):
        raise RuntimeError('CI_EXTERNAL_NETWORK_FORBIDDEN')
    if event == 'socket.getaddrinfo' and external_address((args[0], 0)):
        raise RuntimeError('CI_EXTERNAL_NETWORK_FORBIDDEN')


def install_guard():
    assert_no_credentials()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                      PYTHONDONTWRITEBYTECODE='1', SKN_APP_MODE='cloud')
    sys.addaudithook(network_audit)


def forbid_model(*args, **kwargs):
    raise RuntimeError('CI_MODEL_LOADING_FORBIDDEN')
