import json

import pytest

from ai_mcp_server.application import endpoint_service, metrics
from ai_mcp_server.models.schemas import InvokeResult
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


def _add_model(endpoint_id: int, model_id: str) -> None:
    with connect() as conn:
        dao.upsert_model(conn, endpoint_id, model_id)


def _model_perf(model_id: str) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT performance_json FROM models WHERE model_id=?", (model_id,)
        ).fetchone()
    return json.loads(row["performance_json"]) if row else {}


def _count_events() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM model_call_events").fetchone()["c"]


@pytest.mark.parametrize(
    "body, expected",
    [
        ({"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}, (10, 5, 15)),
        ({"usage": {"input_tokens": 3, "output_tokens": 7}}, (3, 7, None)),
        ({}, (None, None, None)),
    ],
)
def test_extract_token_usage(body, expected):
    assert metrics.extract_token_usage(body) == expected


def test_record_invoke_event_persists_and_updates_performance():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model(ep.id, "model-a")

    result = InvokeResult(
        upstream_status=200,
        body={"usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}},
        latency_ms=500,
    )
    metrics.record_invoke_event(ep.id, "model-a", "chat", result)

    assert _count_events() == 1
    perf = _model_perf("model-a")
    assert perf == {}

    refreshed = metrics.refresh_model_performance(retention_days=1)
    assert refreshed == 1

    perf = _model_perf("model-a")
    assert perf["call_count"] == 1
    assert perf["success_count"] == 1
    assert perf["avg_prompt_tokens"] == 20.0
    assert perf["avg_output_tokens"] == 10.0


def test_refresh_clears_outdated_events_and_resets_performance():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model(ep.id, "model-b")

    with connect() as conn:
        dao.insert_model_call_event(
            conn, ep.id, "model-b", "chat", True, 200, 100, 200, 10, 5, 15, None,
        )

    with connect() as conn:
        conn.execute(
            "UPDATE model_call_events SET created_at=datetime('now', '-5 days')"
        )

    metrics.refresh_model_performance(retention_days=1)
    assert _count_events() == 0

    perf = _model_perf("model-b")
    assert perf == {}


def test_refresh_keeps_events_within_retention_window():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model(ep.id, "model-c")

    with connect() as conn:
        dao.insert_model_call_event(
            conn, ep.id, "model-c", "chat", True, 200, 100, 200, 10, 5, 15, None,
        )
    with connect() as conn:
        conn.execute(
            "UPDATE model_call_events SET created_at=datetime('now', '-5 days')"
        )

    metrics.refresh_model_performance(retention_days=7)
    assert _count_events() == 1
    perf = _model_perf("model-c")
    assert perf["call_count"] == 1
