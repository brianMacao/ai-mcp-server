"""vision probe: send a 1-digit image and ask what character it is."""
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
    if not isinstance(content, str):
        return False
    return "1" in content


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    image_b64 = base.load_digit_image_b64()
    if not image_b64:
        return base.skipped(Capability.VISION, "assets/probe/digit_1.png missing")
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What digit is in this image? Answer with just the digit."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "max_tokens": 8,
        "temperature": 0,
    }
    invoke = await adapter.chat(payload)
    return base.make_result(Capability.VISION, invoke, _structural_ok)
