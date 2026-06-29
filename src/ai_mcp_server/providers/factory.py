"""ProviderAdapter factory keyed by ProviderType."""
from __future__ import annotations

from ..models.enums import ProviderType
from .base import ProviderAdapter
from .openai_compat import OpenAICompatAdapter


def build_adapter(
    provider_type: ProviderType, base_url: str, api_key: str
) -> ProviderAdapter:
    if provider_type is ProviderType.OPENAI_COMPAT:
        return OpenAICompatAdapter(base_url, api_key)
    raise NotImplementedError(f"provider_type={provider_type!r} not yet implemented")
