"""Tests for ``swxsoc_reach.net.auth.resolve_udl_auth``."""

from __future__ import annotations

import json
import os

import pytest

from swxsoc_reach.net import auth


@pytest.fixture(autouse=True)
def _clear_auth_env(monkeypatch):
    """Ensure neither auth env var leaks in from the host environment."""
    monkeypatch.delenv("BASICAUTH", raising=False)
    monkeypatch.delenv("SECRET_ARN_UDL", raising=False)
    yield


def test_resolve_udl_auth_prefers_basicauth_env(monkeypatch):
    monkeypatch.setenv("BASICAUTH", "Basic preset-value")

    # If boto3 is touched at all, fail loudly.
    def boom(*args, **kwargs):
        raise AssertionError("boto3 must not be imported when BASICAUTH is set")

    monkeypatch.setitem(__import__("sys").modules, "boto3", _ExplodingModule(boom))

    assert auth.resolve_udl_auth() == "Basic preset-value"


def test_resolve_udl_auth_raises_when_neither_var_set():
    with pytest.raises(RuntimeError, match="BASICAUTH"):
        auth.resolve_udl_auth()


def test_resolve_udl_auth_uses_secrets_manager(monkeypatch):
    monkeypatch.setenv(
        "SECRET_ARN_UDL", "arn:aws:secretsmanager:us-east-1:123:secret:udl-x"
    )

    captured = {}

    class FakeClient:
        def get_secret_value(self, SecretId):
            captured["SecretId"] = SecretId
            return {"SecretString": json.dumps({"basicauth": "Basic from-aws"})}

    class FakeSession:
        def __init__(self, region_name=None):
            captured["region_name"] = region_name

        def client(self, service_name):
            captured["service_name"] = service_name
            return FakeClient()

    fake_boto3 = _Module()
    fake_boto3.session = _Module()
    fake_boto3.session.Session = FakeSession
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)

    result = auth.resolve_udl_auth(region_name="us-east-1")

    assert result == "Basic from-aws"
    # Side effect: BASICAUTH populated for downstream code.
    assert os.environ["BASICAUTH"] == "Basic from-aws"
    assert captured["SecretId"] == "arn:aws:secretsmanager:us-east-1:123:secret:udl-x"
    assert captured["service_name"] == "secretsmanager"
    assert captured["region_name"] == "us-east-1"


def test_resolve_udl_auth_raises_when_secret_missing_basicauth_key(monkeypatch):
    monkeypatch.setenv(
        "SECRET_ARN_UDL", "arn:aws:secretsmanager:us-east-1:123:secret:udl-x"
    )

    class FakeClient:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({"other_key": "x"})}

    class FakeSession:
        def __init__(self, region_name=None):
            pass

        def client(self, service_name):
            return FakeClient()

    fake_boto3 = _Module()
    fake_boto3.session = _Module()
    fake_boto3.session.Session = FakeSession
    monkeypatch.setitem(__import__("sys").modules, "boto3", fake_boto3)

    with pytest.raises(RuntimeError, match="basicauth"):
        auth.resolve_udl_auth()


def test_resolve_udl_auth_raises_when_boto3_missing(monkeypatch):
    monkeypatch.setenv(
        "SECRET_ARN_UDL", "arn:aws:secretsmanager:us-east-1:123:secret:udl-x"
    )

    import sys

    # Simulate boto3 being absent from the environment.
    monkeypatch.setitem(sys.modules, "boto3", None)

    with pytest.raises(RuntimeError, match="boto3 is not installed"):
        auth.resolve_udl_auth()


# --- helpers ---


class _Module:
    """A lightweight stand-in for a Python module."""


class _ExplodingModule:
    def __init__(self, raiser):
        self._raiser = raiser

    def __getattr__(self, name):
        self._raiser()
