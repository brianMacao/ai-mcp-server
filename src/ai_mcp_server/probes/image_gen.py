"""image generation probe."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    data = body.get("data") or []
    if not data:
        return False
    item = data[0]
    if not isinstance(item, dict):
        return False
    return bool(item.get("url") or item.get("b64_json"))


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "prompt": "A plain white background with the digit 1 in black, centred.",
        "n": 1,
    }
    invoke = await adapter.image_gen(payload)
    return base.make_result(Capability.IMAGE_GEN, invoke, _structural_ok)
