"""Manual model registration for endpoints whose API does not expose /v1/models."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from ..models.enums import ALL_CAPABILITIES, Capability
from ..storage import dao
from ..storage.db import connect

_CAPABILITY_ALIASES: dict[str, Capability] = {
    "chat": Capability.TEXT_CHAT,
    "text": Capability.TEXT_CHAT,
    "text_chat": Capability.TEXT_CHAT,
    "tool": Capability.TOOL_CALL,
    "tool_call": Capability.TOOL_CALL,
    "tools": Capability.TOOL_CALL,
    "vision": Capability.VISION,
    "vl": Capability.VISION,
    "reasoning": Capability.REASONING,
    "reason": Capability.REASONING,
    "json": Capability.JSON_MODE,
    "json_mode": Capability.JSON_MODE,
    "embedding": Capability.EMBEDDING,
    "embed": Capability.EMBEDDING,
    "image": Capability.IMAGE_GEN,
    "image_gen": Capability.IMAGE_GEN,
    "image_generation": Capability.IMAGE_GEN,
    "tts": Capability.AUDIO_TTS,
    "audio_tts": Capability.AUDIO_TTS,
    "speech": Capability.AUDIO_TTS,
    "stt": Capability.AUDIO_STT,
    "asr": Capability.AUDIO_STT,
    "audio_stt": Capability.AUDIO_STT,
    "transcription": Capability.AUDIO_STT,
    "rerank": Capability.RERANK,
    "reranker": Capability.RERANK,
}

_CONTEXT_LENGTH_ALIASES = {"context_length", "context", "ctx"}


def add_models(
    endpoint: str,
    model_ids: list[str],
    context_length: int | None = None,
    capabilities: list[Capability] | None = None,
    feature_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = [m.strip() for m in model_ids if m.strip()]
    if not cleaned:
        return {"error": "no model_id provided"}
    try:
        overrides = normalize_feature_overrides(feature_overrides)
    except ValueError as e:
        return {"error": str(e)}
    if capabilities:
        for cap in capabilities:
            overrides[cap.value] = True
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint)
        if not ep:
            return {"error": f"endpoint {endpoint!r} not found"}
        added: list[str] = []
        for mid in cleaned:
            dao.upsert_model(
                conn,
                endpoint_id=ep.id,
                model_id=mid,
                context_length=context_length,
            )
            for key, value in overrides.items():
                dao.upsert_override(
                    conn,
                    endpoint_id=ep.id,
                    model_id=mid,
                    capability_key=key,
                    value=value,
                )
            added.append(mid)
    return {
        "endpoint": endpoint,
        "added": added,
        "count": len(added),
        "features": overrides,
    }


def remove_model(endpoint: str, model_id: str) -> dict[str, Any]:
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint)
        if not ep:
            return {"error": f"endpoint {endpoint!r} not found"}
        removed = dao.delete_model(conn, ep.id, model_id.strip())
        if removed:
            dao.delete_overrides_for_model(conn, ep.id, model_id.strip())
    return {"endpoint": endpoint, "model_id": model_id, "removed": removed}


def parse_capabilities(raw: str | None) -> list[Capability] | None:
    if not raw:
        return None
    caps: list[Capability] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        caps.append(parse_capability(token))
    return caps or None


def parse_capability(raw: str) -> Capability:
    token = raw.strip().lower()
    if not token:
        raise ValueError("empty capability")
    if token in _CAPABILITY_ALIASES:
        return _CAPABILITY_ALIASES[token]
    return Capability(token)


def parse_feature_overrides(raw: str | Iterable[str] | None) -> dict[str, Any]:
    """Parse user-facing feature registrations from key=value tokens.

    Bare capability tokens are treated as key=true. Values use JSON when possible,
    so true/false/null/numbers keep their native type.
    """
    if raw is None:
        return {}
    tokens: list[str] = []
    if isinstance(raw, str):
        sources = [raw]
    else:
        sources = list(raw)
    for source in sources:
        for token in source.replace("\n", ",").split(","):
            token = token.strip()
            if token:
                tokens.append(token)
    features: dict[str, Any] = {}
    for token in tokens:
        if "=" in token:
            key, raw_value = token.split("=", 1)
            features[key.strip()] = _parse_feature_value(raw_value.strip())
        else:
            features[token] = True
    return normalize_feature_overrides(features)


def normalize_feature_overrides(features: Mapping[str, Any] | None) -> dict[str, Any]:
    if not features:
        return {}
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in features.items():
        key = _normalize_feature_key(str(raw_key))
        normalized[key] = _coerce_feature_value(key, raw_value)
    return normalized


def all_capability_values() -> list[str]:
    return [c.value for c in ALL_CAPABILITIES]


def capability_aliases() -> dict[str, str]:
    return {
        alias: capability.value
        for alias, capability in sorted(_CAPABILITY_ALIASES.items())
        if alias != capability.value
    }


def _normalize_feature_key(raw: str) -> str:
    key = raw.strip().lower()
    if not key:
        raise ValueError("empty feature key")
    if key in _CONTEXT_LENGTH_ALIASES:
        return "context_length"
    try:
        return parse_capability(key).value
    except ValueError:
        allowed = ", ".join(all_capability_values() + ["context_length"])
        raise ValueError(f"unknown feature key {raw!r}; expected one of: {allowed}") from None


def _parse_feature_value(raw: str) -> Any:
    if not raw:
        raise ValueError("feature value cannot be empty")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _coerce_feature_value(key: str, value: Any) -> Any:
    if key == "context_length":
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            raise ValueError("context_length must be an integer") from None
        if parsed <= 0:
            raise ValueError("context_length must be positive")
        return parsed

    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1"}:
            return True
        if lowered in {"false", "no", "n", "0"}:
            return False
    raise ValueError(f"{key} must be a boolean feature value")
