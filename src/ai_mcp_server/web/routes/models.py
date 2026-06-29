"""Model routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...application import capability_query, endpoint_service, manual_models
from ...models.enums import Capability
from ..form_utils import (
    parse_capabilities,
    parse_context_length,
    parse_feature_overrides,
    parse_model_ids,
)

router = APIRouter(prefix="/models")


@router.get("/", response_class=HTMLResponse)
async def model_list(
    request: Request,
    endpoint: str | None = Query(None),
    capability: str | None = Query(None),
    min_context: int | None = Query(None),
) -> HTMLResponse:
    caps: list[Capability] | None = None
    if capability:
        caps = []
        for c in capability.split(","):
            c = c.strip()
            if not c:
                continue
            try:
                caps.append(manual_models.parse_capability(c))
            except ValueError:
                pass
    items = capability_query.query_models(
        capability=caps, min_context_length=min_context, endpoint=endpoint
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "models.html",
        {
            "items": items,
            "endpoints": [e.name for e in endpoint_service.list_endpoints()],
            "filter_endpoint": endpoint or "",
            "filter_capability": capability or "",
            "filter_min_context": min_context or "",
            "all_capabilities": [c.value for c in Capability],
        },
    )


@router.post("/add")
async def model_add(
    endpoint: str = Form(...),
    model_ids: str = Form(...),
    context_length: str = Form(""),
    capability: str = Form(""),
    features: str = Form(""),
) -> RedirectResponse:
    ids = parse_model_ids(model_ids)
    ctx = parse_context_length(context_length)
    caps = parse_capabilities(capability)
    feature_overrides = parse_feature_overrides(features)
    result = manual_models.add_models(endpoint, ids, ctx, caps, feature_overrides)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return RedirectResponse(f"/models/?endpoint={endpoint}", status_code=303)


@router.post("/remove")
async def model_remove(
    endpoint: str = Form(...),
    model_id: str = Form(...),
) -> RedirectResponse:
    result = manual_models.remove_model(endpoint, model_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    if not result["removed"]:
        raise HTTPException(404, f"model {model_id!r} not found on {endpoint}")
    return RedirectResponse(f"/models/?endpoint={endpoint}", status_code=303)


@router.get("/{endpoint}/{model_id:path}", response_class=HTMLResponse)
async def model_detail(endpoint: str, model_id: str, request: Request) -> HTMLResponse:
    detail = capability_query.model_detail(endpoint, model_id)
    if not detail:
        raise HTTPException(404, "model not found")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "model_detail.html", {"detail": detail}
    )
