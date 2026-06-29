"""Model performance query: read aggregated近3天 metrics written by the worker."""
from __future__ import annotations

from typing import Any

from ..storage import dao
from ..storage.db import connect

_SORT_KEYS = {
    "call_count",
    "success_count",
    "avg_first_byte_ms",
    "avg_prompt_tokens",
    "avg_output_tokens",
}


def query_performance(
    endpoint: str | None = None,
    sort_by: str = "call_count",
    limit: int = 50,
) -> list[dict[str, Any]]:
    if sort_by not in _SORT_KEYS:
        sort_by = "call_count"
    with connect() as conn:
        eid: int | None = None
        if endpoint:
            ep = dao.get_endpoint_by_name(conn, endpoint)
            if not ep:
                return []
            eid = ep.id
        models = dao.list_models(conn, endpoint_id=eid)
    rows: list[dict[str, Any]] = []
    for m in models:
        perf = m.performance
        if not perf or perf.get("call_count") is None:
            continue
        success = perf.get("success_count") or 0
        calls = perf.get("call_count") or 0
        rows.append({
            "endpoint": m.endpoint_name,
            "model_id": m.model_id,
            "full_id": m.full_id,
            "call_count": calls,
            "success_count": success,
            "success_rate": round(success / calls, 4) if calls else None,
            "avg_first_byte_ms": perf.get("avg_first_byte_ms"),
            "avg_prompt_tokens": perf.get("avg_prompt_tokens"),
            "avg_output_tokens": perf.get("avg_output_tokens"),
            "window_days": perf.get("window_days"),
        })
    ascending = sort_by == "avg_first_byte_ms"
    rows.sort(
        key=lambda r: (
            r.get(sort_by) is None,
            (r.get(sort_by) or 0.0) if ascending else -(r.get(sort_by) or 0.0),
        )
    )
    return rows[:limit]
