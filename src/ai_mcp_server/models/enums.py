"""Shared enums for capabilities, probe status, job status, provider types."""
from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    TEXT_CHAT = "text_chat"
    TOOL_CALL = "tool_call"
    VISION = "vision"
    REASONING = "reasoning"
    JSON_MODE = "json_mode"
    EMBEDDING = "embedding"
    IMAGE_GEN = "image_gen"
    AUDIO_TTS = "audio_tts"
    AUDIO_STT = "audio_stt"
    RERANK = "rerank"


ALL_CAPABILITIES: tuple[Capability, ...] = tuple(Capability)


class ProbeStatus(StrEnum):
    OK = "ok"
    NOT_SUPPORTED = "not_supported"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


class CapabilitySource(StrEnum):
    OVERRIDE = "override"
    PROBE = "probe"
    LITELLM = "litellm"
    STATIC = "static"


class JobStatus(StrEnum):
    PENDING = "pending"
    CLAIMING = "claiming"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ProviderType(StrEnum):
    OPENAI_COMPAT = "openai-compat"
    # Reserved:
    # ANTHROPIC = "anthropic"
