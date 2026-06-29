"""audio STT probe."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    txt = body.get("text")
    return isinstance(txt, str) and len(txt) > 0


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    audio = base.load_digit_audio_bytes()
    if not audio:
        return base.skipped(Capability.AUDIO_STT, "assets/probe/digit_1.wav missing")
    wav_bytes, filename = audio
    payload = {
        "model": model_id,
        "file_bytes": wav_bytes,
        "file_name": filename,
    }
    invoke = await adapter.stt(payload)
    return base.make_result(Capability.AUDIO_STT, invoke, _structural_ok)
