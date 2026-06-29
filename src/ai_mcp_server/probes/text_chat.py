"""text_chat probe: ask the model to reply with '1' only."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    choices = body.get("choices") or []
    if not choices:
        return False
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    return isinstance(content, str) and len(content) > 0


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "Reply with only the digit 1. No other text."},
        ],
        "max_tokens": 8,
        "temperature": 0,
    }
    invoke = await adapter.chat(payload)
    return base.make_result(Capability.TEXT_CHAT, invoke, _structural_ok)
