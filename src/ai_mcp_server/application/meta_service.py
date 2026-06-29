"""LiteLLM metadata refresh wrapper."""
from __future__ import annotations

from ..capability import litellm_meta


def refresh() -> int:
    return litellm_meta.refresh_from_remote()


def info() -> dict[str, int]:
    data = litellm_meta.load()
    return {"entries": len(data)}
