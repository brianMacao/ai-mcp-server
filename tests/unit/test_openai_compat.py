import base64

import pytest

from ai_mcp_server.providers.openai_compat import OpenAICompatAdapter


class _FakeResponse:
    status_code = 200
    content = b"audio"
    headers = {"content-type": "audio/mpeg"}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs):
        return _FakeResponse()


@pytest.mark.asyncio
async def test_tts_success_returns_audio_base64(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    adapter = OpenAICompatAdapter("https://example.com/v1", "sk")
    result = await adapter.tts({"model": "tts", "input": "one", "voice": "alloy"})

    assert result.ok
    assert result.body["audio_base64"] == base64.b64encode(b"audio").decode("ascii")
    assert result.body["audio_bytes_len"] == 5
    assert result.body["content_type"] == "audio/mpeg"
