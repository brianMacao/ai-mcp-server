from ai_mcp_server.application import endpoint_service, probe_jobs
from ai_mcp_server.models.enums import Capability
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


def _add_model(endpoint_id: int, model_id: str) -> None:
    with connect() as conn:
        dao.upsert_model(conn, endpoint_id, model_id)


def _job_caps() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT model_id, capability FROM probe_jobs ORDER BY model_id, capability"
        ).fetchall()
    return [f"{row['model_id']}:{row['capability']}" for row in rows]


def test_smart_enqueue_selects_capabilities_per_model_family():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    for model_id in [
        "meta/llama-3.1-8b-instruct",
        "meta/llama-3.2-11b-vision-instruct",
        "baai/bge-m3",
        "nvidia/nv-rerankqa-mistral-4b-v3",
        "doubao-seedream-5.0-lite",
    ]:
        _add_model(ep.id, model_id)

    jids = probe_jobs.enqueue_for_endpoint(
        ep.id,
        [
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.2-11b-vision-instruct",
            "baai/bge-m3",
            "nvidia/nv-rerankqa-mistral-4b-v3",
            "doubao-seedream-5.0-lite",
        ],
    )

    assert len(jids) == 6
    assert _job_caps() == [
        "baai/bge-m3:embedding",
        "doubao-seedream-5.0-lite:image_gen",
        "meta/llama-3.1-8b-instruct:text_chat",
        "meta/llama-3.2-11b-vision-instruct:text_chat",
        "meta/llama-3.2-11b-vision-instruct:vision",
        "nvidia/nv-rerankqa-mistral-4b-v3:rerank",
    ]


def test_explicit_capabilities_override_smart_selection():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model(ep.id, "baai/bge-m3")

    jids = probe_jobs.enqueue_for_endpoint(
        ep.id,
        ["baai/bge-m3"],
        [Capability.TEXT_CHAT, Capability.TOOL_CALL],
    )

    assert len(jids) == 2
    assert _job_caps() == [
        "baai/bge-m3:text_chat",
        "baai/bge-m3:tool_call",
    ]


def test_probe_plan_reports_smart_selection_without_enqueueing():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    _add_model(ep.id, "meta/llama-3.2-11b-vision-instruct")

    plan = probe_jobs.probe_plan(ep.id, ["meta/llama-3.2-11b-vision-instruct"])

    assert plan == [
        {
            "model_id": "meta/llama-3.2-11b-vision-instruct",
            "capabilities": ["text_chat", "vision"],
        }
    ]
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM probe_jobs").fetchone()["c"]
    assert count == 0
