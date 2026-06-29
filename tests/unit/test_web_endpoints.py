from fastapi.testclient import TestClient

from ai_mcp_server.application import endpoint_service
from ai_mcp_server.capability import resolver
from ai_mcp_server.models.enums import (
    ALL_CAPABILITIES,
    Capability,
    CapabilitySource,
    JobStatus,
)
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect
from ai_mcp_server.web.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_endpoint_detail_has_manual_add_form():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().get("/endpoints/nv")
    assert resp.status_code == 200
    assert "手動新增 model" in resp.text


def test_endpoint_add_model_route():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/endpoints/nv/models/add",
        data={
            "model_ids": "manual-a, manual-b",
            "context_length": "4096",
            "features": "tts=true,asr=false",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    with connect() as conn:
        models = {m.model_id: m for m in dao.list_models(conn, endpoint_id=ep.id)}
    assert set(models) == {"manual-a", "manual-b"}
    assert models["manual-a"].context_length == 4096
    with connect() as conn:
        caps = resolver.resolve(conn, models["manual-a"])
    assert caps[Capability.AUDIO_TTS].value is True
    assert caps[Capability.AUDIO_STT].value is False


def test_endpoint_remove_model_route():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "to-del")
    resp = _client().post(
        "/endpoints/nv/models/remove",
        data={"model_id": "to-del"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    with connect() as conn:
        assert dao.get_model(conn, ep.id, "to-del") is None


def test_endpoint_probe_enqueues_all_capabilities_for_all_models():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "chat-model")
        dao.upsert_model(conn, ep.id, "embed-model")

    resp = _client().post("/endpoints/nv/probe", follow_redirects=False)

    assert resp.status_code == 303
    with connect() as conn:
        jobs = dao.list_jobs(conn, status=JobStatus.PENDING, limit=1000)
    by_model = {
        model_id: {job.capability for job in jobs if job.model_id == model_id}
        for model_id in {"chat-model", "embed-model"}
    }
    assert len(jobs) == 2 * len(ALL_CAPABILITIES)
    assert by_model == {
        "chat-model": set(ALL_CAPABILITIES),
        "embed-model": set(ALL_CAPABILITIES),
    }


def test_endpoint_probe_model_enqueues_smart_jobs():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "chat-model")
    resp = _client().post(
        "/endpoints/nv/models/probe",
        data={"model_id": "chat-model"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    with connect() as conn:
        jobs = dao.list_jobs(conn, status=JobStatus.PENDING)
    assert any(j.model_id == "chat-model" for j in jobs)


def test_endpoint_detail_shows_probe_negative_capabilities():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "gpt-4o")
        dao.update_model_capability(
            conn,
            ep.id,
            "gpt-4o",
            "vision",
            False,
            CapabilitySource.PROBE,
            probed_at="2026-06-29",
        )

    resp = _client().get("/endpoints/nv")

    assert resp.status_code == 200
    assert "vision=false(pro)" in resp.text


def test_endpoint_add_model_rejects_empty_ids():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/endpoints/nv/models/add",
        data={"model_ids": "  "},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_endpoint_add_model_rejects_unknown_endpoint():
    resp = _client().post(
        "/endpoints/no-such-ep/models/add",
        data={"model_ids": "m1"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_endpoint_add_model_rejects_invalid_context():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/endpoints/nv/models/add",
        data={"model_ids": "m1", "context_length": "abc"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_endpoint_remove_model_returns_404_for_missing():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/endpoints/nv/models/remove",
        data={"model_id": "not-there"},
        follow_redirects=False,
    )
    assert resp.status_code == 404
