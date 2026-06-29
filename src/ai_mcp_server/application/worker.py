"""Worker: claim → 0.5s verify → execute → write back.

Implements the optimistic lock described in the PRD §5.6:
1. Conditional UPDATE writing claimed_by=instance_id.
2. Sleep 0.5s.
3. SELECT claimed_by; only continue if still == instance_id.
4. Otherwise yield (someone else won the race).
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

from ..models.enums import CapabilitySource, ProbeStatus
from ..probes import REGISTRY as PROBE_REGISTRY
from ..probes.base import skipped
from ..providers.factory import build_adapter
from ..storage import dao
from ..storage.db import connect
from . import metrics

logger = logging.getLogger("ai_mcp_server.worker")

LEASE_SECONDS = 300  # 5 min default lease per job
CLAIM_VERIFY_WAIT_SEC = 0.5
SWEEP_INTERVAL_SEC = 30
METRICS_REFRESH_INTERVAL_SEC = 30
IDLE_POLL_SEC = 2


def _now_plus(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class Worker:
    """Single-instance worker. Multiple workers may coexist via optimistic lock."""

    def __init__(self, instance_id: str | None = None, metrics_retention_days: int = metrics.DEFAULT_RETENTION_DAYS) -> None:
        self.instance_id = instance_id or str(uuid.uuid4())
        self.metrics_retention_days = metrics_retention_days
        self._stop = asyncio.Event()

    async def claim_one(self) -> int | None:
        """Try to claim one pending job. Returns job_id or None."""
        with connect() as conn:
            job_id = dao.next_pending_job_id(conn)
            if job_id is None:
                return None
            wrote = dao.claim_job_attempt(
                conn, job_id, self.instance_id, _now_plus(LEASE_SECONDS)
            )
            if not wrote:
                return None
        # 0.5 sec safety window for any concurrent claimers.
        await asyncio.sleep(CLAIM_VERIFY_WAIT_SEC)
        with connect() as conn:
            owner = dao.get_claimed_by(conn, job_id)
            if owner != self.instance_id:
                logger.debug("job %s ceded to %s", job_id, owner)
                return None
            dao.mark_job_running(conn, job_id)
        return job_id

    async def run_job(self, job_id: int) -> None:
        with connect() as conn:
            job = dao.get_job(conn, job_id)
        if job is None:
            return
        try:
            with connect() as conn:
                row = conn.execute(
                    "SELECT name, base_url, provider_type, api_key_enc FROM endpoints WHERE id=?",
                    (job.endpoint_id,),
                ).fetchone()
            if row is None:
                with connect() as conn:
                    dao.mark_job_done(conn, job_id, error="endpoint missing")
                return
            from ..models.enums import ProviderType
            from ..storage import crypto

            adapter = build_adapter(
                ProviderType(row["provider_type"]),
                row["base_url"],
                crypto.decrypt(row["api_key_enc"]),
            )
            logger.info(
                "probe starting job_id=%s endpoint=%s endpoint_id=%s model=%s capability=%s instance_id=%s",
                job.id,
                row["name"],
                job.endpoint_id,
                job.model_id,
                job.capability.value,
                self.instance_id,
            )
            probe_fn = PROBE_REGISTRY.get(job.capability)
            if not probe_fn:
                result = skipped(job.capability, "no probe registered")
            else:
                result = await probe_fn(adapter, job.model_id)
            with connect() as conn:
                dao.insert_probe_run(conn, job.endpoint_id, job.model_id, result)
                if result.status in {ProbeStatus.OK, ProbeStatus.NOT_SUPPORTED}:
                    dao.update_model_capability(
                        conn,
                        endpoint_id=job.endpoint_id,
                        model_id=job.model_id,
                        capability=job.capability.value,
                        value=result.ok,
                        source=CapabilitySource.PROBE,
                        probed_at=_now(),
                    )
                terminal_error = (
                    result.error
                    if result.status
                    in {
                        ProbeStatus.RATE_LIMITED,
                        ProbeStatus.TIMEOUT,
                        ProbeStatus.ERROR,
                        ProbeStatus.SKIPPED,
                    }
                    else None
                )
                dao.mark_job_done(conn, job_id, error=terminal_error)
        except Exception as exc:
            logger.exception("worker job %s crashed", job_id)
            with connect() as conn:
                try:
                    dao.mark_job_done(conn, job_id, error=str(exc))
                except sqlite3.Error:
                    pass

    def refresh_metrics(self) -> int:
        return metrics.refresh_model_performance(self.metrics_retention_days)

    async def drain(self) -> int:
        """Consume queue until empty. Returns count of jobs processed."""
        self.refresh_metrics()
        count = 0
        while not self._stop.is_set():
            jid = await self.claim_one()
            if jid is None:
                # No pending job available to this worker right now.
                with connect() as conn:
                    remaining = dao.next_pending_job_id(conn)
                if remaining is None:
                    break
                await asyncio.sleep(IDLE_POLL_SEC)
                continue
            await self.run_job(jid)
            count += 1
        self.refresh_metrics()
        return count

    async def run_loop(self) -> None:
        """Long-running loop: claim or wait; sweep orphans periodically."""
        refreshed = self.refresh_metrics()
        logger.info("refreshed performance metrics for %d model(s)", refreshed)
        last_sweep = 0.0
        last_metrics_refresh = 0.0
        while not self._stop.is_set():
            now_mono = asyncio.get_event_loop().time()
            if now_mono - last_sweep > SWEEP_INTERVAL_SEC:
                with connect() as conn:
                    swept = dao.sweep_orphans(conn)
                if swept:
                    logger.info("swept %d orphan jobs", swept)
                last_sweep = now_mono
            if now_mono - last_metrics_refresh > METRICS_REFRESH_INTERVAL_SEC:
                self.refresh_metrics()
                last_metrics_refresh = now_mono
            jid = await self.claim_one()
            if jid is None:
                await asyncio.sleep(IDLE_POLL_SEC)
                continue
            await self.run_job(jid)

    def request_stop(self) -> None:
        self._stop.set()


async def drain_blocking(metrics_retention_days: int = metrics.DEFAULT_RETENTION_DAYS) -> int:
    """Convenience: drain queue in current event loop, return processed count."""
    w = Worker(metrics_retention_days=metrics_retention_days)
    return await w.drain()
