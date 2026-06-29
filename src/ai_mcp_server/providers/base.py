"""Provider adapter abstraction. OpenAICompat is the only concrete impl in v1;
Anthropic is reserved by keeping the interface OpenAI-superset shaped.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models.schemas import InvokeResult


class ProviderAdapter(ABC):
    """Protocol-agnostic adapter. All payloads are dict[str, Any], passed through."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """Return raw items from GET /v1/models (or equivalent)."""

    @abstractmethod
    async def chat(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/chat/completions (non-streaming)."""

    @abstractmethod
    async def embedding(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/embeddings."""

    @abstractmethod
    async def image_gen(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/images/generations."""

    @abstractmethod
    async def tts(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/audio/speech. Returns bytes inside body if successful."""

    @abstractmethod
    async def stt(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/audio/transcriptions. Multipart-aware."""

    @abstractmethod
    async def rerank(self, payload: dict[str, Any]) -> InvokeResult:
        """POST /v1/rerank (vendor-specific path may apply)."""
