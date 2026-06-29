"""Overrides routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...application import manual_models, override_service
from ...storage import dao
from ...storage.db import connect

router = APIRouter(prefix="/overrides")


@router.get("/", response_class=HTMLResponse)
async def overrides_list(request: Request) -> HTMLResponse:
    rows: list[dict] = []
    with connect() as conn:
        for ep in dao.list_endpoints(conn):
            cur = conn.execute(
                "SELECT model_id, capability_key, value_json, updated_at "
                "FROM overrides WHERE endpoint_id=?",
                (ep.id,),
            )
            for r in cur.fetchall():
                rows.append({
                    "endpoint": ep.name,
                    "model_id": r["model_id"],
                    "capability_key": r["capability_key"],
                    "value": r["value_json"],
                    "updated_at": r["updated_at"],
                })
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "overrides.html", {"rows": rows}
    )


@router.post("/")
async def overrides_add(
    endpoint: str = Form(...),
    model_id: str = Form(...),
    capability_key: str = Form(...),
    value: str = Form(...),
) -> RedirectResponse:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value
    try:
        normalized = manual_models.normalize_feature_overrides({capability_key: parsed})
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    key, parsed_value = next(iter(normalized.items()))
    override_service.set_override(endpoint, model_id, key, parsed_value)
    return RedirectResponse("/overrides/", status_code=303)


@router.post("/delete")
async def overrides_delete(
    endpoint: str = Form(...),
    model_id: str = Form(...),
    capability_key: str = Form(...),
) -> RedirectResponse:
    override_service.delete_override(endpoint, model_id, capability_key)
    return RedirectResponse("/overrides/", status_code=303)
