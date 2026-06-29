import logging

import pytest

from ai_mcp_server.application import endpoint_service, probe_jobs
from ai_mcp_server.application.worker import Worker
from ai_mcp_server.capability.resolver import resolve
from ai_mcp_server.models.enums import Capability, ProbeStatus
from ai_mcp_server.models.schemas import ProbeResult
from ai_mcp_server.probes import REGISTRY
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


@pytest.mark.asyncio
async def test_worker_logs_job_details_before_probe(monkeypatch, caplog):
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    job_id = probe_jobs.enqueue_for_endpoint(ep.id, ["model-a"], [Capability.TEXT_CHAT])[0]
    with connect() as conn:
        dao.mark_job_running(conn, job_id)

    async def fake_probe(adapter, model_id):
        return ProbeResult(
            capability=Capability.TEXT_CHAT,
            status=ProbeStatus.OK,
            ok=True,
            latency_ms=1,
            raw={"model_id": model_id},
        )

    monkeypatch.setitem(REGISTRY, Capability.TEXT_CHAT, fake_probe)

    caplog.set_level(logging.INFO, logger="ai_mcp_server.worker")
    await Worker(instance_id="worker-test").run_job(job_id)

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "probe starting job_id=" in message
        and "endpoint=nv" in message
        and "model=model-a" in message
        and "capability=text_chat" in message
        and "instance_id=worker-test" in message
        for message in messages
    )


@pytest.mark.asyncio
async def test_worker_does_not_pollute_capability_on_probe_timeout(monkeypatch):
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "gpt-4o")
    job_id = probe_jobs.enqueue_for_endpoint(ep.id, ["gpt-4o"], [Capability.VISION])[0]
    with connect() as conn:
        dao.mark_job_running(conn, job_id)

    async def fake_probe(adapter, model_id):
        return ProbeResult(
            capability=Capability.VISION,
            status=ProbeStatus.TIMEOUT,
            ok=False,
            latency_ms=1000,
            error="timeout",
        )

    monkeypatch.setitem(REGISTRY, Capability.VISION, fake_probe)

    await Worker(instance_id="worker-test").run_job(job_id)

    with connect() as conn:
        model = dao.get_model(conn, ep.id, "gpt-4o")
        assert model is not None
        caps = resolve(conn, model)
        runs = dao.list_probe_runs(conn, endpoint_id=ep.id, model_id="gpt-4o")
        job = dao.get_job(conn, job_id)

    assert caps[Capability.VISION].value is True
    assert caps[Capability.VISION].source.value == "static"
    assert runs[0]["status"] == "timeout"
    assert job is not None
    assert job.status.value == "failed"
