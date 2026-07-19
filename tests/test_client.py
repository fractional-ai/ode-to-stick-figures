import pytest

import lib.client as client_mod


def test_beta_constant_present():
    assert isinstance(client_mod.MANAGED_AGENTS_BETA, str)
    assert client_mod.MANAGED_AGENTS_BETA


def test_managed_client_sets_beta_header(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    c = client_mod.managed_client()
    # The beta header must be on the client so every beta.* call carries it.
    # Read default_headers directly: the SDK keeps the caller-supplied
    # default_headers here (not on the internal _client.headers).
    headers = c.default_headers
    joined = " ".join(f"{k}:{v}" for k, v in dict(headers).items())
    assert client_mod.MANAGED_AGENTS_BETA in joined


def test_managed_client_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        client_mod.managed_client()
