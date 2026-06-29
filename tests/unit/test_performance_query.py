import json

from ai_mcp_server.application import endpoint_service, performance_query
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


def _add_model_with_perf(endpoint_id: int, model_id: str, perf: dict | None) -> None:
    with connect() as conn:
        dao.upsert_model(conn, endpoint_id, model_id)
        if perf is not None:
            conn.execute(
                "UPDATE models SET performance_json=? WHERE endpoint_id=? AND model_id=?",
                (json.dumps(perf), endpoint_id, model_id),
            )


def test_query_performance_filters_models_without_metrics():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model_with_perf(ep.id, "model-empty", None)
    _add_model_with_perf(ep.id, "model-a", {
        "window_days": 3, "call_count": 5, "success_count": 4,
        "avg_first_byte_ms": 300.0, "avg_prompt_tokens": 20.0, "avg_output_tokens": 10.0,
    })

    rows = performance_query.query_performance(endpoint="nv")
    assert [r["model_id"] for r in rows] == ["model-a"]
    assert rows[0]["success_rate"] == 0.8


def test_query_performance_sort_by_call_count_desc_and_latency_asc():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model_with_perf(ep.id, "low-calls", {
        "window_days": 3, "call_count": 2, "success_count": 2,
        "avg_first_byte_ms": 100.0, "avg_prompt_tokens": 1.0, "avg_output_tokens": 1.0,
    })
    _add_model_with_perf(ep.id, "high-calls", {
        "window_days": 3, "call_count": 9, "success_count": 9,
        "avg_first_byte_ms": 800.0, "avg_prompt_tokens": 1.0, "avg_output_tokens": 1.0,
    })

    by_calls = performance_query.query_performance(sort_by="call_count")
    assert [r["model_id"] for r in by_calls] == ["high-calls", "low-calls"]

    by_latency = performance_query.query_performance(sort_by="avg_first_byte_ms")
    assert [r["model_id"] for r in by_latency] == ["low-calls", "high-calls"]


def test_query_performance_unknown_endpoint_returns_empty():
    assert performance_query.query_performance(endpoint="missing") == []
