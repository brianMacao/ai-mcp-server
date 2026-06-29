"""audio TTS probe."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    return bool(body.get("audio_bytes_len"))


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "input": "one",
        "voice": "alloy",
        "response_format": "mp3",
    }
    invoke = await adapter.tts(payload)
    return base.make_result(Capability.AUDIO_TTS, invoke, _structural_ok)
