"""LiteLLM metadata routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...application import meta_service

router = APIRouter(prefix="/meta")


@router.get("/", response_class=HTMLResponse)
async def meta_info(request: Request) -> HTMLResponse:
    info = meta_service.info()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "meta.html", {"info": info}
    )


@router.post("/refresh")
async def meta_refresh() -> RedirectResponse:
    try:
        meta_service.refresh()
    except Exception as e:
        raise HTTPException(500, f"refresh failed: {e}") from None
    return RedirectResponse("/meta/", status_code=303)
