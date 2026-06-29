"""Dashboard route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ...application import capability_query, endpoint_service, probe_jobs

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    eps = endpoint_service.list_endpoints()
    models = capability_query.query_models()
    cap_counts: dict[str, int] = {}
    for it in models:
        for cap, cv in it["capabilities"].items():
            if cv.get("value"):
                cap_counts[cap] = cap_counts.get(cap, 0) + 1
    from ...models.enums import JobStatus

    pending = len(probe_jobs.list_jobs(status=JobStatus.PENDING, limit=10000))
    running = len(probe_jobs.list_jobs(status=JobStatus.RUNNING, limit=10000))
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "endpoints": eps,
            "model_count": len(models),
            "cap_counts": dict(sorted(cap_counts.items())),
            "pending": pending,
            "running": running,
        },
    )
