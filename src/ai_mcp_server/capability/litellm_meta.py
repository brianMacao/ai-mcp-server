"""LiteLLM metadata loader.

For v1 we ship an empty snapshot and provide a refresh hook. The presence of
this layer guarantees the resolver always has a third-priority source even if
the network is unavailable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..utils.path_util import litellm_metadata_path

_REMOTE_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "litellm/model_prices_and_context_window_backup.json"
)


def _cache_path() -> Path:
    return litellm_metadata_path()


def load() -> dict[str, dict[str, Any]]:
    """Return the cached LiteLLM metadata mapping (model_id -> meta dict)."""
    p = _cache_path()
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, dict)}
    return {}


def refresh_from_remote(timeout: float = 30.0) -> int:
    """Pull latest snapshot from upstream and cache locally. Returns entry count."""
    import httpx

    resp = httpx.get(_REMOTE_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    data = resp.json()
    _cache_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(data) if isinstance(data, dict) else 0


def lookup(model_id: str, data: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Best-effort match: exact, then 'provider/model_id' suffix."""
    if data is None:
        data = load()
    if not data:
        return None
    if model_id in data:
        return data[model_id]
    # Try matching tail after any '/'
    for k, v in data.items():
        if "/" in k and k.endswith("/" + model_id):
            return v
    return None
