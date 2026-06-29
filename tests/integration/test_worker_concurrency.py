"""Optimistic-lock concurrency test: two workers racing for jobs.

Goal: each pending job is processed by exactly one worker (no double-execution),
and all jobs reach a terminal state.
"""
from __future__ import annotations

import asyncio

import pytest

from ai_mcp_server.application import endpoint_service, probe_jobs
from ai_mcp_server.application import worker as worker_mod
from ai_mcp_server.application.worker import Worker
from ai_mcp_server.models.enums import Capability
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


@pytest.mark.asyncio
async def test_two_workers_no_double_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch the probe run logic so we don't hit the network.
    executions: list[tuple[str, int]] = []

    async def fake_run_job(self: Worker, job_id: int) -> None:
        executions.append((self.instance_id, job_id))
        with connect() as conn:
            dao.mark_job_done(conn, job_id)

    monkeypatch.setattr(Worker, "run_job", fake_run_job)
    # Speed up the verification window.
    monkeypatch.setattr(worker_mod, "CLAIM_VERIFY_WAIT_SEC", 0.05)
    monkeypatch.setattr(worker_mod, "IDLE_POLL_SEC", 0.05)

    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    enq = probe_jobs.enqueue_for_endpoint(
        ep.id, [f"m-{i}" for i in range(20)], [Capability.TEXT_CHAT]
    )
    assert len(enq) == 20

    w1 = Worker()
    w2 = Worker()
    res = await asyncio.gather(w1.drain(), w2.drain())

    # Combined should equal job count, with no job executed twice.
    job_ids = [jid for _wid, jid in executions]
    assert sorted(job_ids) == sorted(enq), f"missing or duplicate: {job_ids}"
    assert sum(res) == len(enq)

    # All jobs should be terminal.
    with connect() as conn:
        rows = conn.execute(
            "SELECT status FROM probe_jobs"
        ).fetchall()
    statuses = [r["status"] for r in rows]
    assert all(s in {"done", "failed"} for s in statuses), statuses
