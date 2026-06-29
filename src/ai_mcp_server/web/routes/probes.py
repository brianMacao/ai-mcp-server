"""probe_runs (history) routes."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from ...storage import dao
from ...storage.db import connect

router = APIRouter(prefix="/probes")


@router.get("/", response_class=HTMLResponse)
async def probes_list(
    request: Request,
    endpoint: str | None = Query(None),
    model_id: str | None = Query(None),
    capability: str | None = Query(None),
    limit: int = Query(200),
) -> HTMLResponse:
    eid: int | None = None
    with connect() as conn:
        if endpoint:
            ep = dao.get_endpoint_by_name(conn, endpoint)
            eid = ep.id if ep else -1
        rows = dao.list_probe_runs(
            conn, endpoint_id=eid, model_id=model_id, capability=capability, limit=limit
        )
        eps = dao.list_endpoints(conn)
    name_by_id = {e.id: e.name for e in eps}
    for r in rows:
        r["endpoint_name"] = name_by_id.get(r["endpoint_id"], str(r["endpoint_id"]))
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "probes.html", {"rows": rows}
    )
