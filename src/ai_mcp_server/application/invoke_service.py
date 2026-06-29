"""invoke_model: forward request via provider adapter, wrap result."""
from __future__ import annotations

from typing import Any

from .endpoint_service import build_adapter_for
from .metrics import record_invoke_event


async def invoke(
    endpoint: str,
    model: str,
    operation: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _ep, adapter = build_adapter_for(endpoint)
    op = operation.lower()
    body = {**payload, "model": model}
    if op == "chat":
        res = await adapter.chat(body)
    elif op == "embedding":
        res = await adapter.embedding(body)
    elif op == "image_gen":
        res = await adapter.image_gen(body)
    elif op == "tts":
        res = await adapter.tts(body)
    elif op == "stt":
        res = await adapter.stt(body)
    elif op == "rerank":
        res = await adapter.rerank(body)
    else:
        return {"error": {"type": "bad_operation", "message": f"unknown operation {operation!r}"}}
    record_invoke_event(_ep.id, model, op, res)
    out: dict[str, Any] = {
        "_meta": {
            "endpoint": endpoint,
            "model": model,
            "operation": op,
            "latency_ms": res.latency_ms,
            "first_byte_ms": res.first_byte_ms if res.first_byte_ms is not None else res.latency_ms,
            "upstream_status": res.upstream_status,
        },
    }
    if res.error:
        out["error"] = res.error
    else:
        out["body"] = res.body
    return out
