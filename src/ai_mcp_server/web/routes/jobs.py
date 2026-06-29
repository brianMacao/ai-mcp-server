"""probe_jobs routes + SSE progress stream."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ...application import probe_jobs
from ...storage import dao
from ...storage.db import connect

router = APIRouter(prefix="/jobs")


@router.get("/", response_class=HTMLResponse)
async def jobs_list(request: Request) -> HTMLResponse:
    jobs = probe_jobs.list_jobs(limit=200)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "jobs.html", {"jobs": jobs}
    )


@router.get("/stream")
async def jobs_stream(request: Request) -> StreamingResponse:
    """SSE stream of job summary every 1 second."""

    async def _gen() -> AsyncGenerator[bytes, None]:
        last_event_id = request.headers.get("last-event-id")
        seq = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0
        while True:
            if await request.is_disconnected():
                break
            with connect() as conn:
                counts = {}
                for s in ("pending", "claiming", "running", "done", "failed"):
                    row = conn.execute(
                        "SELECT COUNT(*) AS c FROM probe_jobs WHERE status=?", (s,)
                    ).fetchone()
                    counts[s] = row["c"]
                last_jobs = dao.list_jobs(conn, limit=10)
            payload = {
                "counts": counts,
                "recent": [
                    {
                        "id": j.id,
                        "endpoint_id": j.endpoint_id,
                        "model_id": j.model_id,
                        "capability": j.capability.value,
                        "status": j.status.value,
                        "error": j.error,
                    }
                    for j in last_jobs
                ],
            }
            data = json.dumps(payload, ensure_ascii=False)
            yield f"id: {seq}\nevent: snapshot\ndata: {data}\n\n".encode()
            seq += 1
            await asyncio.sleep(1.0)

    return StreamingResponse(_gen(), media_type="text/event-stream")
