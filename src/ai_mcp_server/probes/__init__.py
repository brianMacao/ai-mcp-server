"""Capability -> probe function registry."""
from __future__ import annotations

from ..models.enums import Capability
from . import (
    audio_stt,
    audio_tts,
    base,
    embedding,
    image_gen,
    json_mode,
    reasoning,
    rerank,
    text_chat,
    tool_call,
    vision,
)

REGISTRY: dict[Capability, base.ProbeFn] = {
    Capability.TEXT_CHAT: text_chat.probe,
    Capability.TOOL_CALL: tool_call.probe,
    Capability.VISION: vision.probe,
    Capability.REASONING: reasoning.probe,
    Capability.JSON_MODE: json_mode.probe,
    Capability.EMBEDDING: embedding.probe,
    Capability.IMAGE_GEN: image_gen.probe,
    Capability.AUDIO_TTS: audio_tts.probe,
    Capability.AUDIO_STT: audio_stt.probe,
    Capability.RERANK: rerank.probe,
}

__all__ = ["REGISTRY", "base"]
