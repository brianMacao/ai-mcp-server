"""embedding probe."""
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
    emb = data[0].get("embedding") if isinstance(data[0], dict) else None
    return isinstance(emb, list) and len(emb) > 0


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {"model": model_id, "input": "1"}
    invoke = await adapter.embedding(payload)
    return base.make_result(Capability.EMBEDDING, invoke, _structural_ok)
