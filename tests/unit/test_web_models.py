from fastapi.testclient import TestClient

from ai_mcp_server.application import endpoint_service
from ai_mcp_server.capability import resolver
from ai_mcp_server.models.enums import Capability
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect
from ai_mcp_server.web.app import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_models_add_route_registers_models():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    client = _client()

    resp = client.post(
        "/models/add",
        data={
            "endpoint": "nv",
            "model_ids": "ui-model-a, ui-model-b",
            "context_length": "16000",
            "capability": "text_chat",
            "features": "asr=true",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with connect() as conn:
        models = {m.model_id: m for m in dao.list_models(conn, endpoint_id=ep.id)}
    assert set(models) == {"ui-model-a", "ui-model-b"}
    assert models["ui-model-a"].context_length == 16000
    with connect() as conn:
        caps = resolver.resolve(conn, models["ui-model-a"])
    assert caps[Capability.TEXT_CHAT].value is True
    assert caps[Capability.AUDIO_STT].value is True


def test_models_remove_route_deletes_model():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "ui-model-x")
    client = _client()

    resp = client.post(
        "/models/remove",
        data={"endpoint": "nv", "model_id": "ui-model-x"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    with connect() as conn:
        assert dao.get_model(conn, ep.id, "ui-model-x") is None


def test_models_list_route_renders():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "no-perf-model")
    client = _client()
    resp = client.get("/models/")
    assert resp.status_code == 200
    assert "手動新增 model" in resp.text
    assert "no-perf-model" in resp.text


def test_model_detail_route_renders_without_performance():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "no-perf-model")
    client = _client()
    resp = client.get("/models/nv/no-perf-model")
    assert resp.status_code == 200
    assert "近 3 天暫無調用記錄" in resp.text


def test_overrides_route_normalizes_feature_alias():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "manual-model")

    resp = _client().post(
        "/overrides/",
        data={
            "endpoint": "nv",
            "model_id": "manual-model",
            "capability_key": "tts",
            "value": "true",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    with connect() as conn:
        model = dao.get_model(conn, ep.id, "manual-model")
        assert model is not None
        caps = resolver.resolve(conn, model)
    assert caps[Capability.AUDIO_TTS].value is True


def test_models_add_rejects_unknown_endpoint():
    resp = _client().post(
        "/models/add",
        data={"endpoint": "no-such-ep", "model_ids": "m1"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_models_add_rejects_invalid_capability():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/models/add",
        data={"endpoint": "nv", "model_ids": "m1", "capability": "not-a-cap"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_models_remove_returns_404_for_missing():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    resp = _client().post(
        "/models/remove",
        data={"endpoint": "nv", "model_id": "not-there"},
        follow_redirects=False,
    )
    assert resp.status_code == 404
