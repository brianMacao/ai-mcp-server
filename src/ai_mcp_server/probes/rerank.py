"""rerank probe."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..models.schemas import ProbeResult
from ..providers.base import ProviderAdapter
from . import base


def _structural_ok(body: Any) -> bool:
    if not isinstance(body, dict):
        return False
    results = body.get("results") or body.get("data") or []
    if not isinstance(results, list) or not results:
        return False
    first = results[0]
    if not isinstance(first, dict):
        return False
    return ("relevance_score" in first) or ("score" in first) or ("index" in first)


async def probe(adapter: ProviderAdapter, model_id: str) -> ProbeResult:
    payload = {
        "model": model_id,
        "query": "What is 1?",
        "documents": ["The number 1.", "An unrelated sentence about cats."],
        "top_n": 2,
    }
    invoke = await adapter.rerank(payload)
    return base.make_result(Capability.RERANK, invoke, _structural_ok)
