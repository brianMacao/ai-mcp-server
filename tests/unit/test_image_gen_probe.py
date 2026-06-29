from typing import Any

import pytest

from ai_mcp_server.models.schemas import InvokeResult
from ai_mcp_server.probes import image_gen


class RecordingAdapter:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    async def image_gen(self, payload: dict[str, Any]) -> InvokeResult:
        self.payload = payload
        return InvokeResult(
            upstream_status=200,
            body={"data": [{"url": "https://example.com/1.png"}]},
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_image_gen_probe_uses_minimal_openai_payload():
    adapter = RecordingAdapter()

    result = await image_gen.probe(adapter, "doubao-seedream-5.0-lite")

    assert result.ok is True
    assert adapter.payload == {
        "model": "doubao-seedream-5.0-lite",
        "prompt": "A plain white background with the digit 1 in black, centred.",
        "n": 1,
    }
