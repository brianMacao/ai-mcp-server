"""Shared form parsing helpers for Web UI routes."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..application import manual_models
from ..models.enums import Capability


def parse_model_ids(raw: str) -> list[str]:
    ids = [m.strip() for m in raw.replace(",", "\n").splitlines() if m.strip()]
    if not ids:
        raise HTTPException(400, "at least one model_id is required")
    return ids


def parse_context_length(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise HTTPException(400, "context_length must be an integer") from None
    if value <= 0:
        raise HTTPException(400, "context_length must be positive")
    return value


def parse_capabilities(raw: str) -> list[Capability] | None:
    try:
        return manual_models.parse_capabilities(raw)
    except ValueError as e:
        raise HTTPException(400, f"unknown capability: {e}") from None


def parse_feature_overrides(raw: str) -> dict[str, Any]:
    try:
        return manual_models.parse_feature_overrides(raw)
    except ValueError as e:
        raise HTTPException(400, f"invalid feature override: {e}") from None
