from fastapi.testclient import TestClient

from ai_mcp_server.web.app import create_app


def test_ui_token_protects_jobs_stream(monkeypatch):
    monkeypatch.setenv("AI_MCP_UI_TOKEN", "secret")
    client = TestClient(create_app())

    resp = client.get("/jobs/stream")

    assert resp.status_code == 401


def test_ui_token_allows_normal_page_with_token(monkeypatch):
    monkeypatch.setenv("AI_MCP_UI_TOKEN", "secret")
    client = TestClient(create_app())

    resp = client.get("/jobs/?token=secret")

    assert resp.status_code == 200
