"""Endpoint CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...application import endpoint_service, manual_models, model_discovery, probe_jobs
from ...models.enums import ProviderType
from ..form_utils import parse_context_length, parse_feature_overrides, parse_model_ids

router = APIRouter(prefix="/endpoints")


@router.get("/", response_class=HTMLResponse)
async def endpoint_list(request: Request) -> HTMLResponse:
    items = endpoint_service.list_endpoints()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "endpoints.html", {"endpoints": items}
    )


@router.post("/")
async def endpoint_add(
    name: str = Form(...),
    base_url: str = Form(...),
    key: str = Form(...),
    provider_type: str = Form("openai-compat"),
) -> RedirectResponse:
    try:
        endpoint_service.add_endpoint(name, base_url, key, ProviderType(provider_type))
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return RedirectResponse("/endpoints/", status_code=303)


@router.get("/{name}", response_class=HTMLResponse)
async def endpoint_detail(name: str, request: Request) -> HTMLResponse:
    ep = endpoint_service.get_endpoint(name)
    if not ep:
        raise HTTPException(404, "endpoint not found")
    from ...application import capability_query

    models = capability_query.query_models(endpoint=name)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "endpoint_detail.html",
        {"endpoint": ep, "models": models},
    )


@router.post("/{name}/delete")
async def endpoint_remove(name: str) -> RedirectResponse:
    endpoint_service.remove_endpoint(name)
    return RedirectResponse("/endpoints/", status_code=303)


@router.post("/{name}/discover")
async def endpoint_discover(name: str) -> RedirectResponse:
    await model_discovery.discover(name)
    return RedirectResponse(f"/endpoints/{name}", status_code=303)


@router.post("/{name}/probe")
async def endpoint_probe(name: str) -> RedirectResponse:
    ep = endpoint_service.get_endpoint(name)
    if not ep:
        raise HTTPException(404, "endpoint not found")
    from ...storage import dao
    from ...storage.db import connect

    with connect() as conn:
        models = dao.list_models(conn, endpoint_id=ep.id)
    model_ids = [m.model_id for m in models]
    if not model_ids:
        raise HTTPException(404, "no models registered on this endpoint")
    probe_jobs.enqueue_for_endpoint(ep.id, model_ids, probe_jobs.all_probe_capabilities())
    return RedirectResponse("/jobs/", status_code=303)


@router.post("/{name}/models/add")
async def endpoint_add_model(
    name: str,
    model_ids: str = Form(...),
    context_length: str = Form(""),
    features: str = Form(""),
) -> RedirectResponse:
    ids = parse_model_ids(model_ids)
    ctx = parse_context_length(context_length)
    feature_overrides = parse_feature_overrides(features)
    result = manual_models.add_models(name, ids, ctx, None, feature_overrides)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return RedirectResponse(f"/endpoints/{name}", status_code=303)


@router.post("/{name}/models/remove")
async def endpoint_remove_model(
    name: str,
    model_id: str = Form(...),
) -> RedirectResponse:
    result = manual_models.remove_model(name, model_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    if not result["removed"]:
        raise HTTPException(404, f"model {model_id!r} not found on {name}")
    return RedirectResponse(f"/endpoints/{name}", status_code=303)


@router.post("/{name}/models/probe")
async def endpoint_probe_model(
    name: str,
    model_id: str = Form(...),
) -> RedirectResponse:
    ep = endpoint_service.get_endpoint(name)
    if not ep:
        raise HTTPException(404, "endpoint not found")
    mid = model_id.strip()
    if not mid:
        raise HTTPException(400, "model_id is required")
    probe_jobs.enqueue_for_endpoint(ep.id, [mid])
    return RedirectResponse("/jobs/", status_code=303)
