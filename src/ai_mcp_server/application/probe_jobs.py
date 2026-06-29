"""probe_jobs enqueue / list helpers."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import Any

from ..capability import resolver, static_map
from ..models.enums import ALL_CAPABILITIES, Capability, JobStatus
from ..models.schemas import ModelDTO, ProbeJobDTO
from ..storage import dao
from ..storage.db import connect

_CHAT_PROBES = {
    Capability.TEXT_CHAT,
    Capability.TOOL_CALL,
    Capability.VISION,
    Capability.REASONING,
    Capability.JSON_MODE,
}
_SPECIAL_KEYWORDS: tuple[tuple[Capability, tuple[str, ...]], ...] = (
    (Capability.RERANK, ("rerank", "reranker", "ranking")),
    (Capability.EMBEDDING, ("embed", "embedding", "bge", "e5", "jina-embeddings")),
    (Capability.IMAGE_GEN, ("image-gen", "image_gen", "image-generation", "diffusion", "flux", "dall-e", "stable-diffusion", "seedream")),
    (Capability.AUDIO_STT, ("whisper", "stt", "transcribe", "transcription")),
    (Capability.AUDIO_TTS, ("tts", "speech", "audio-speech")),
)
_VISION_KEYWORDS = (
    "vision",
    "vl",
    "multimodal",
    "fuyu",
    "kosmos",
    "deplot",
    "vila",
    "neva",
    "nvclip",
)
_REASONING_KEYWORDS = ("reasoning", "reason", "r1", "o1", "o3")


def _ordered_caps(caps: Iterable[Capability]) -> list[Capability]:
    wanted = set(caps)
    return [cap for cap in ALL_CAPABILITIES if cap in wanted]


def all_probe_capabilities() -> list[Capability]:
    """Return the full probe suite in the stable enum order."""
    return list(ALL_CAPABILITIES)


def _bool_meta_capabilities(conn: sqlite3.Connection, model: ModelDTO) -> set[Capability]:
    return {
        cap
        for cap, value in resolver.resolve(conn, model).items()
        if bool(value.value)
    }


def select_probe_capabilities(conn: sqlite3.Connection, model: ModelDTO) -> list[Capability]:
    """Choose a conservative probe set for one model using known metadata and name hints."""
    model_id = model.model_id.lower()
    known = _bool_meta_capabilities(conn, model)
    static_known = set(static_map.lookup_capabilities(model.model_id))
    selected: set[Capability] = set()

    for cap, keywords in _SPECIAL_KEYWORDS:
        if cap in known or any(keyword in model_id for keyword in keywords):
            return [cap]

    if Capability.VISION in known or any(keyword in model_id for keyword in _VISION_KEYWORDS):
        selected.update({Capability.TEXT_CHAT, Capability.VISION})

    if Capability.REASONING in known or any(keyword in model_id for keyword in _REASONING_KEYWORDS):
        selected.update({Capability.TEXT_CHAT, Capability.REASONING})

    chat_known = known & _CHAT_PROBES
    if chat_known:
        selected.update(chat_known)
        if selected & {Capability.TOOL_CALL, Capability.JSON_MODE, Capability.VISION, Capability.REASONING}:
            selected.add(Capability.TEXT_CHAT)

    if not selected and (static_known or _looks_like_chat_model(model_id)):
        selected.add(Capability.TEXT_CHAT)

    if not selected:
        selected.add(Capability.TEXT_CHAT)

    return _ordered_caps(selected)


def _looks_like_chat_model(model_id: str) -> bool:
    non_chat_hints = {
        "embed",
        "embedding",
        "rerank",
        "reranker",
        "diffusion",
        "image",
        "whisper",
        "tts",
        "speech",
        "parse",
    }
    if any(hint in model_id for hint in non_chat_hints):
        return False
    chat_hints = {
        "chat",
        "instruct",
        "llama",
        "mistral",
        "mixtral",
        "qwen",
        "gemma",
        "deepseek",
        "phi",
        "glm",
        "kimi",
        "nemotron",
        "granite",
        "jamba",
    }
    return any(hint in model_id for hint in chat_hints)


def enqueue_for_endpoint(
    endpoint_id: int,
    model_ids: list[str],
    capabilities: list[Capability] | None = None,
    priority: int = 0,
) -> list[int]:
    """Enqueue probe jobs; explicit capabilities are honored, otherwise selected per model."""
    job_ids: list[int] = []
    with connect() as conn:
        models_by_id = {m.model_id: m for m in dao.list_models(conn, endpoint_id=endpoint_id)}
        for mid in model_ids:
            model = models_by_id.get(mid)
            caps = list(capabilities) if capabilities is not None else (
                select_probe_capabilities(conn, model) if model else [Capability.TEXT_CHAT]
            )
            for cap in caps:
                job_ids.append(
                    dao.enqueue_job(conn, endpoint_id, mid, cap, priority)
                )
    return job_ids


def list_jobs(status: JobStatus | None = None, limit: int = 200) -> list[ProbeJobDTO]:
    with connect() as conn:
        return dao.list_jobs(conn, status=status, limit=limit)


def probe_plan(endpoint_id: int, model_ids: list[str]) -> list[dict[str, Any]]:
    with connect() as conn:
        models_by_id = {m.model_id: m for m in dao.list_models(conn, endpoint_id=endpoint_id)}
        out: list[dict[str, Any]] = []
        for mid in model_ids:
            model = models_by_id.get(mid)
            caps = select_probe_capabilities(conn, model) if model else [Capability.TEXT_CHAT]
            out.append({
                "model_id": mid,
                "capabilities": [cap.value for cap in caps],
            })
        return out
