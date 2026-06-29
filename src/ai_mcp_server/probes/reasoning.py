"""reasoning probe: detect presence of reasoning_content in response."""
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
    # OpenAI o-series style returns reasoning content in choices[].message.reasoning_content
    # or under usage.completion_tokens_details.reasoning_tokens.
    if "reasoning_content" in msg and msg["reasoning_content"]:
        return True
    usage = body.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    if details.get("reasoning_tokens"):
        return True
    return False


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": "What is 1+1? Show your reasoning, then answer."},
        ],
        "max_tokens": 256,
        "temperature": 0,
    }
    invoke = await adapter.chat(payload)
    return base.make_result(Capability.REASONING, invoke, _structural_ok)
