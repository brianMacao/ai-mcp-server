from __future__ import annotations

import logging
from typing import Any

from ..models.schemas import InvokeResult
from ..storage import dao
from ..storage.db import connect

logger = logging.getLogger("ai_mcp_server.metrics")
DEFAULT_RETENTION_DAYS = 3


def _usage(body: Any) -> dict[str, Any]:
    if isinstance(body, dict) and isinstance(body.get("usage"), dict):
        return body["usage"]
    return {}


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def extract_token_usage(body: Any) -> tuple[int | None, int | None, int | None]:
    usage = _usage(body)
    prompt_tokens = _int_or_none(usage.get("prompt_tokens") or usage.get("input_tokens"))
    output_tokens = _int_or_none(
        usage.get("completion_tokens") or usage.get("output_tokens")
    )
    total_tokens = _int_or_none(usage.get("total_tokens"))
    return prompt_tokens, output_tokens, total_tokens


def record_invoke_event(
    endpoint_id: int,
    model_id: str,
    operation: str,
    result: InvokeResult,
) -> None:
    prompt_tokens, output_tokens, total_tokens = extract_token_usage(result.body)
    error_type = None
    if isinstance(result.error, dict):
        value = result.error.get("type")
        error_type = value if isinstance(value, str) else None
    first_byte_ms = result.first_byte_ms if result.first_byte_ms is not None else result.latency_ms
    try:
        with connect() as conn:
            dao.insert_model_call_event(
                conn,
                endpoint_id=endpoint_id,
                model_id=model_id,
                operation=operation,
                ok=result.ok,
                upstream_status=result.upstream_status,
                first_byte_ms=first_byte_ms,
                latency_ms=result.latency_ms,
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                error_type=error_type,
            )
    except Exception:
        logger.exception("failed to record invoke metrics endpoint_id=%s model=%s", endpoint_id, model_id)


def refresh_model_performance(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    with connect() as conn:
        dao.delete_model_call_events_older_than(conn, retention_days)
        return dao.aggregate_model_performance(conn, retention_days)
