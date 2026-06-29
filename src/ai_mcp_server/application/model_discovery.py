"""Pull /v1/models from upstream, upsert into local DB."""
from __future__ import annotations

from ..storage import dao
from ..storage.db import connect
from . import endpoint_service


async def discover(endpoint_name: str) -> list[str]:
    """Fetch list of model_ids from upstream and write to DB."""
    ep, adapter = endpoint_service.build_adapter_for(endpoint_name)
    items = await adapter.list_models()
    discovered: list[str] = []
    with connect() as conn:
        for item in items:
            model_id = (
                item.get("id") if isinstance(item, dict) else None
            ) or (item if isinstance(item, str) else None)
            if not model_id:
                continue
            ctx = None
            if isinstance(item, dict):
                for key in ("context_length", "context_window", "max_input_tokens"):
                    v = item.get(key)
                    if isinstance(v, int) and v > 0:
                        ctx = v
                        break
            dao.upsert_model(
                conn,
                endpoint_id=ep.id,
                model_id=model_id,
                raw_meta=item if isinstance(item, dict) else None,
                context_length=ctx,
            )
            discovered.append(model_id)
    return discovered
