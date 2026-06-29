"""verification_script: probe a known NVIDIA NIM model and inspect results."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make sure src is importable when running directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ai_mcp_server.application import endpoint_service  # noqa: E402
from ai_mcp_server.application import worker as worker_mod  # noqa: E402
from ai_mcp_server.models.enums import Capability  # noqa: E402
from ai_mcp_server.storage import dao  # noqa: E402
from ai_mcp_server.storage.db import connect  # noqa: E402

TARGETS = [
    # (model_id, capability) tuples to probe
    ("meta/llama-3.1-8b-instruct", Capability.TEXT_CHAT),
    ("meta/llama-3.1-8b-instruct", Capability.TOOL_CALL),
    ("nvidia/nv-embedqa-e5-v5", Capability.EMBEDDING),
]


async def main() -> int:
    ep = endpoint_service.get_endpoint("nvidia")
    if not ep:
        print("endpoint 'nvidia' not registered", file=sys.stderr)
        return 1
    # Ensure target models exist locally (upsert with no metadata).
    with connect() as conn:
        for model_id, _cap in TARGETS:
            dao.upsert_model(conn, ep.id, model_id)

    job_ids = []
    for model_id, cap in TARGETS:
        with connect() as conn:
            jid = dao.enqueue_job(conn, ep.id, model_id, cap)
        job_ids.append((jid, model_id, cap.value))
        print(f"enqueued job {jid}: {model_id} / {cap.value}")

    print("draining queue ...")
    processed = await worker_mod.drain_blocking()
    print(f"processed {processed} jobs")

    with connect() as conn:
        for jid, model_id, capn in job_ids:
            job = dao.get_job(conn, jid)
            runs = dao.list_probe_runs(
                conn, endpoint_id=ep.id, model_id=model_id, capability=capn, limit=1
            )
            run = runs[0] if runs else None
            print(json.dumps({
                "job_id": jid,
                "model_id": model_id,
                "capability": capn,
                "job_status": job.status.value if job else None,
                "job_error": job.error if job else None,
                "probe_status": run["status"] if run else None,
                "probe_ok": bool(run["ok"]) if run else None,
                "latency_ms": run["latency_ms"] if run else None,
                "error": run["error"] if run else None,
            }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
