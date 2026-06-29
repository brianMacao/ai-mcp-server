"""Four-source capability resolver.

Priority (highest first):
1. user override (DB table 'overrides')
2. probe result (stored inside models.capabilities_json with source='probe')
3. third-party metadata (LiteLLM snapshot)
4. built-in static map (model_id substring rules)
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..models.enums import ALL_CAPABILITIES, Capability, CapabilitySource
from ..models.schemas import CapabilityValue, ModelDTO
from ..storage import dao
from . import litellm_meta, static_map


def _from_litellm(meta: dict[str, Any]) -> dict[Capability, Any]:
    caps: dict[Capability, Any] = {}
    if meta.get("supports_function_calling"):
        caps[Capability.TOOL_CALL] = True
    if meta.get("supports_vision"):
        caps[Capability.VISION] = True
    if meta.get("supports_response_schema") or meta.get("supports_json_mode"):
        caps[Capability.JSON_MODE] = True
    if meta.get("supports_reasoning"):
        caps[Capability.REASONING] = True
    mode = (meta.get("mode") or "").lower()
    if mode in {"chat", "completion"}:
        caps[Capability.TEXT_CHAT] = True
    if mode == "embedding":
        caps[Capability.EMBEDDING] = True
    if mode == "image_generation":
        caps[Capability.IMAGE_GEN] = True
    if mode == "audio_speech":
        caps[Capability.AUDIO_TTS] = True
    if mode == "audio_transcription":
        caps[Capability.AUDIO_STT] = True
    if mode == "rerank":
        caps[Capability.RERANK] = True
    return caps


def resolve(
    conn: sqlite3.Connection, model: ModelDTO
) -> dict[Capability, CapabilityValue]:
    """Compute the effective capability map for a single model."""
    result: dict[Capability, CapabilityValue] = {}

    static = static_map.lookup_capabilities(model.model_id)
    for cap, val in static.items():
        result[cap] = CapabilityValue(value=val, source=CapabilitySource.STATIC)

    litellm = litellm_meta.lookup(model.model_id)
    if litellm:
        for cap, val in _from_litellm(litellm).items():
            result[cap] = CapabilityValue(value=val, source=CapabilitySource.LITELLM)

    for cap_key, cap_val in model.capabilities.items():
        if cap_val.source is CapabilitySource.PROBE:
            try:
                cap_enum = Capability(cap_key)
            except ValueError:
                continue
            result[cap_enum] = cap_val

    overrides = dao.list_overrides(conn, model.endpoint_id, model.model_id)
    for ok, ov in overrides.items():
        try:
            cap_enum = Capability(ok)
        except ValueError:
            continue
        result[cap_enum] = CapabilityValue(value=ov, source=CapabilitySource.OVERRIDE)

    return result


def resolve_context_length(
    conn: sqlite3.Connection, model: ModelDTO
) -> tuple[int | None, CapabilitySource | None]:
    """Resolve context_length with same priority chain."""
    overrides = dao.list_overrides(conn, model.endpoint_id, model.model_id)
    if "context_length" in overrides:
        return int(overrides["context_length"]), CapabilitySource.OVERRIDE
    if model.context_length:
        return model.context_length, CapabilitySource.PROBE
    litellm = litellm_meta.lookup(model.model_id)
    if litellm:
        for key in ("max_input_tokens", "max_tokens"):
            v = litellm.get(key)
            if isinstance(v, int) and v > 0:
                return v, CapabilitySource.LITELLM
    static_ctx = static_map.lookup_context_length(model.model_id)
    if static_ctx:
        return static_ctx, CapabilitySource.STATIC
    return None, None


def filter_models(
    conn: sqlite3.Connection,
    models: list[ModelDTO],
    require_capabilities: list[Capability] | None = None,
    min_context_length: int | None = None,
) -> list[dict[str, Any]]:
    """Resolve + filter; return list of plain dicts for serialisation."""
    out: list[dict[str, Any]] = []
    for m in models:
        caps = resolve(conn, m)
        ctx, ctx_src = resolve_context_length(conn, m)
        if require_capabilities:
            if not all(caps.get(c) and bool(caps[c].value) for c in require_capabilities):
                continue
        if min_context_length and (ctx is None or ctx < min_context_length):
            continue
        cap_dump: dict[str, dict[str, Any]] = {}
        for c in ALL_CAPABILITIES:
            if c in caps:
                cv = caps[c]
                cap_dump[c.value] = {
                    "value": cv.value,
                    "source": cv.source.value,
                    "probed_at": cv.probed_at,
                }
        out.append({
            "endpoint": m.endpoint_name,
            "model_id": m.model_id,
            "full_id": m.full_id,
            "capabilities": cap_dump,
            "context_length": ctx,
            "context_length_source": ctx_src.value if ctx_src else None,
            "performance": m.performance,
            "last_discovered_at": m.last_discovered_at,
        })
    return out
