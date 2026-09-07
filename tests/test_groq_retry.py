"""C1 — Groq retry/backoff: retries on rate limit/timeout/5xx, never on
auth/malformed-request errors, capped total retry time, retry logging,
and no silent model downgrade."""
import asyncio
import logging

import httpx
import pytest

from services import groq_client


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status, request=request, text=f"error {status}")
    return httpx.HTTPStatusError(f"status {status}", request=request, response=response)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _ok_chat_response(content="hello") -> _FakeResponse:
    return _FakeResponse({"choices": [{"message": {"content": content}}]})


class _ScriptedAsyncClient:
    """Fake httpx.AsyncClient — replays a scripted sequence of
    responses/exceptions on successive .post() calls, tracking the model
    sent on each call so tests can assert it never silently changes."""

    _script: list = []
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None, **kwargs):
        type(self).calls.append(json.get("model") if json else None)
        item = type(self)._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    """Retry backoff would otherwise really sleep — make it instant."""
    async def _instant_sleep(_seconds):
        return None
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    _ScriptedAsyncClient._script = []
    _ScriptedAsyncClient.calls = []
    monkeypatch.setattr(groq_client.httpx, "AsyncClient", _ScriptedAsyncClient)
    yield


async def test_retries_on_429_then_succeeds():
    _ScriptedAsyncClient._script = [_status_error(429), _ok_chat_response("ok")]
    result = await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert result == "ok"
    assert len(_ScriptedAsyncClient.calls) == 2


async def test_retries_on_5xx_then_succeeds():
    _ScriptedAsyncClient._script = [_status_error(503), _ok_chat_response("ok")]
    result = await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert result == "ok"


async def test_retries_on_timeout_then_succeeds():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    _ScriptedAsyncClient._script = [httpx.ConnectTimeout("timed out", request=request), _ok_chat_response("ok")]
    result = await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert result == "ok"


async def test_no_retry_on_auth_error():
    _ScriptedAsyncClient._script = [_status_error(401)]
    with pytest.raises(httpx.HTTPStatusError):
        await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert len(_ScriptedAsyncClient.calls) == 1


async def test_no_retry_on_malformed_request_error():
    _ScriptedAsyncClient._script = [_status_error(400)]
    with pytest.raises(httpx.HTTPStatusError):
        await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert len(_ScriptedAsyncClient.calls) == 1


async def test_retry_capped_at_3_attempts():
    _ScriptedAsyncClient._script = [_status_error(429), _status_error(429), _status_error(429), _ok_chat_response("ok")]
    with pytest.raises(httpx.HTTPStatusError):
        await groq_client.chat("m", "sys", "user", agent_name="problem")
    assert len(_ScriptedAsyncClient.calls) == 3  # never reaches the 4th (would-be-successful) call


async def test_never_changes_model_across_retries():
    """No cheaper-model fallback: every retry attempt sends the exact same
    model as the first — per-agent score anchoring depends on this."""
    _ScriptedAsyncClient._script = [_status_error(429), _status_error(503), _ok_chat_response("ok")]
    await groq_client.chat("llama-3.3-70b-versatile", "sys", "user", agent_name="problem")
    assert _ScriptedAsyncClient.calls == ["llama-3.3-70b-versatile"] * 3


async def test_retry_logs_agent_name_and_attempt(caplog):
    caplog.set_level(logging.WARNING, logger="notaflop.groq_client")
    _ScriptedAsyncClient._script = [_status_error(429), _ok_chat_response("ok")]
    await groq_client.chat("m", "sys", "user", agent_name="yc_signal")
    assert "groq_retry" in caplog.text
    assert "agent=yc_signal" in caplog.text
    assert "attempt=1" in caplog.text


async def test_defaults_to_unknown_agent_when_not_supplied(caplog):
    caplog.set_level(logging.WARNING, logger="notaflop.groq_client")
    _ScriptedAsyncClient._script = [_status_error(429), _ok_chat_response("ok")]
    await groq_client.chat("m", "sys", "user")
    assert "agent=unknown" in caplog.text
