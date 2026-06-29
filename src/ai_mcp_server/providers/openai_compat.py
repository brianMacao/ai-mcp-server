"""OpenAI-compatible HTTP adapter. Pass-through semantics, no body rewriting."""
from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from ..models.schemas import InvokeResult
from .base import ProviderAdapter

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class OpenAICompatAdapter(ProviderAdapter):
    """Speaks the OpenAI REST flavour. Works with OpenAI, NVIDIA NIM, OpenRouter,
    Together, DeepSeek, Moonshot, SiliconFlow, vLLM, Ollama, etc."""

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self.base_url}/models", headers=self._headers())
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and "data" in body:
            return list(body["data"])
        if isinstance(body, list):
            return body
        return []

    async def _post_json(
        self, path: str, payload: dict[str, Any]
    ) -> InvokeResult:
        url = f"{self.base_url}{path}"
        headers = self._headers({"Content-Type": "application/json"})
        # Force non-streaming.
        if "stream" in payload:
            payload = {**payload, "stream": False}
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as e:
            return InvokeResult(
                upstream_status=0,
                body=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error={"type": "timeout", "message": str(e)},
            )
        except httpx.HTTPError as e:
            return InvokeResult(
                upstream_status=0,
                body=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error={"type": "http_error", "message": str(e)},
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        body: Any
        try:
            body = resp.json()
        except ValueError:
            body = {"raw_text": resp.text}
        if 200 <= resp.status_code < 300:
            return InvokeResult(upstream_status=resp.status_code, body=body, latency_ms=latency_ms)
        return InvokeResult(
            upstream_status=resp.status_code,
            body=body,
            latency_ms=latency_ms,
            error={
                "type": "upstream_error",
                "status": resp.status_code,
                "body": body,
            },
        )

    async def chat(self, payload: dict[str, Any]) -> InvokeResult:
        return await self._post_json("/chat/completions", payload)

    async def embedding(self, payload: dict[str, Any]) -> InvokeResult:
        return await self._post_json("/embeddings", payload)

    async def image_gen(self, payload: dict[str, Any]) -> InvokeResult:
        return await self._post_json("/images/generations", payload)

    async def tts(self, payload: dict[str, Any]) -> InvokeResult:
        # Many vendors return audio/* bytes here; treat non-JSON as raw bytes.
        url = f"{self.base_url}/audio/speech"
        headers = self._headers({"Content-Type": "application/json"})
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            return InvokeResult(
                upstream_status=0, body=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error={"type": "http_error", "message": str(e)},
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        if 200 <= resp.status_code < 300:
            return InvokeResult(
                upstream_status=resp.status_code,
                body={
                    "audio_base64": base64.b64encode(resp.content).decode("ascii"),
                    "audio_bytes_len": len(resp.content),
                    "content_type": resp.headers.get("content-type"),
                },
                latency_ms=latency_ms,
            )
        try:
            body: Any = resp.json()
        except ValueError:
            body = {"raw_text": resp.text}
        return InvokeResult(
            upstream_status=resp.status_code, body=body, latency_ms=latency_ms,
            error={"type": "upstream_error", "status": resp.status_code, "body": body},
        )

    async def stt(self, payload: dict[str, Any]) -> InvokeResult:
        """Multipart upload. payload expects 'file_bytes', 'file_name', 'model'."""
        url = f"{self.base_url}/audio/transcriptions"
        headers = self._headers()  # let httpx set Content-Type
        files = {"file": (payload["file_name"], payload["file_bytes"], "audio/wav")}
        data = {k: v for k, v in payload.items() if k not in ("file_bytes", "file_name")}
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, files=files, data=data)
        except httpx.HTTPError as e:
            return InvokeResult(
                upstream_status=0, body=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error={"type": "http_error", "message": str(e)},
            )
        latency_ms = int((time.perf_counter() - start) * 1000)
        try:
            body: Any = resp.json()
        except ValueError:
            body = {"raw_text": resp.text}
        if 200 <= resp.status_code < 300:
            return InvokeResult(upstream_status=resp.status_code, body=body, latency_ms=latency_ms)
        return InvokeResult(
            upstream_status=resp.status_code, body=body, latency_ms=latency_ms,
            error={"type": "upstream_error", "status": resp.status_code, "body": body},
        )

    async def rerank(self, payload: dict[str, Any]) -> InvokeResult:
        # Many vendors expose /v1/rerank or /v1/reranking. Try /rerank by default.
        return await self._post_json("/rerank", payload)
