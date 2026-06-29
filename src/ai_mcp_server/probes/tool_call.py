"""tool_call probe: ask model to call a fake tool."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "echo_digit",
        "description": "Echo back a digit.",
        "parameters": {
            "type": "object",
            "properties": {
                "digit": {"type": "integer", "description": "A single digit 0-9"},
            },
            "required": ["digit"],
        },
    },
}


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    choices = body.get("choices") or []
    if not choices:
        return False
    msg = choices[0].get("message") or {}
    tcs = msg.get("tool_calls")
    return isinstance(tcs, list) and len(tcs) > 0


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "Call echo_digit with digit=1."},
        ],
        "tools": [_TOOL_SCHEMA],
        "tool_choice": "auto",
        "max_tokens": 64,
        "temperature": 0,
    }
    invoke = await adapter.chat(payload)
    return base.make_result(Capability.TOOL_CALL, invoke, _structural_ok)
