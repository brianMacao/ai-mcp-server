"""json_mode probe: use response_format=json_object and check for valid JSON."""
from __future__ import annotations

import json
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
    content = (choices[0].get("message") or {}).get("content") or ""
    if not isinstance(content, str):
        return False
    try:
        json.loads(content)
        return True
    except (ValueError, TypeError):
        return False


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "Reply with a JSON object only."},
            {"role": "user", "content": "Return {\"answer\": 1}"},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 32,
        "temperature": 0,
    }
    invoke = await adapter.chat(payload)
    return base.make_result(Capability.JSON_MODE, invoke, _structural_ok)
