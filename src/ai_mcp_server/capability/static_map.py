"""Built-in static capability map: model_id prefix -> capability set.

This is the bottom of the four-source resolver. Keep it conservative: only assert
capabilities that are documented for the entire prefix family.
"""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability

# Each entry: (prefix_or_substring, {capability: value})
# Matching is "substring in model_id, case-insensitive".
_RULES: list[tuple[str, dict[Capability, Any]]] = [
    # OpenAI family
    ("gpt-4o", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True,
        Capability.VISION: True, Capability.JSON_MODE: True,
    }),
    ("gpt-4-turbo", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True,
        Capability.VISION: True, Capability.JSON_MODE: True,
    }),
    ("gpt-4", {Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True, Capability.JSON_MODE: True}),
    ("gpt-3.5", {Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True}),
    ("o1", {Capability.TEXT_CHAT: True, Capability.REASONING: True}),
    ("o3", {Capability.TEXT_CHAT: True, Capability.REASONING: True}),
    ("text-embedding", {Capability.EMBEDDING: True}),
    ("dall-e", {Capability.IMAGE_GEN: True}),
    ("seedream", {Capability.IMAGE_GEN: True}),
    ("whisper", {Capability.AUDIO_STT: True}),
    ("tts-1", {Capability.AUDIO_TTS: True}),
    ("seed-tts-2.0", {Capability.AUDIO_TTS: True}),
    ("volc.seedasr.sauc.duration", {Capability.AUDIO_STT: True}),

    # Anthropic via OpenAI-compat gateways
    ("claude-3", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True, Capability.VISION: True,
    }),
    ("claude-sonnet", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True, Capability.VISION: True,
    }),
    ("claude-opus", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True, Capability.VISION: True,
    }),

    # Google Gemini via OpenAI-compat gateways
    ("gemini-", {
        Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True, Capability.VISION: True,
    }),

    # DeepSeek
    ("deepseek-chat", {Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True}),
    ("deepseek-coder", {Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True}),
    ("deepseek-r1", {Capability.TEXT_CHAT: True, Capability.REASONING: True}),

    # Qwen
    ("qwen", {Capability.TEXT_CHAT: True}),
    ("qwen2.5-vl", {Capability.TEXT_CHAT: True, Capability.VISION: True}),
    ("qwen-vl", {Capability.TEXT_CHAT: True, Capability.VISION: True}),

    # Moonshot
    ("moonshot-v1", {Capability.TEXT_CHAT: True, Capability.TOOL_CALL: True}),
    ("kimi", {Capability.TEXT_CHAT: True}),

    # Embedding families
    ("bge-", {Capability.EMBEDDING: True}),
    ("bge-reranker", {Capability.RERANK: True}),
    ("e5-", {Capability.EMBEDDING: True}),

    # Meta Llama (via NIM/together/openrouter)
    ("llama-3", {Capability.TEXT_CHAT: True}),
    ("llama3", {Capability.TEXT_CHAT: True}),

    # Mistral
    ("mistral", {Capability.TEXT_CHAT: True}),
    ("mixtral", {Capability.TEXT_CHAT: True}),

    # NVIDIA NIM specific
    ("nv-rerank", {Capability.RERANK: True}),
    ("nv-embed", {Capability.EMBEDDING: True}),
]

# Context length hints (model_id substring -> default context window).
_CONTEXT_HINTS: list[tuple[str, int]] = [
    ("gpt-4o", 128000),
    ("gpt-4-turbo", 128000),
    ("gpt-4", 8192),
    ("gpt-3.5-turbo", 16385),
    ("o1", 128000),
    ("o3", 128000),
    ("claude-3-5", 200000),
    ("claude-3", 200000),
    ("claude-sonnet", 200000),
    ("claude-opus", 200000),
    ("gemini-1.5-pro", 2000000),
    ("gemini-1.5-flash", 1000000),
    ("deepseek-chat", 64000),
    ("deepseek-coder", 64000),
    ("deepseek-r1", 64000),
    ("qwen2.5-72b", 131072),
    ("qwen2.5", 32768),
    ("moonshot-v1-128k", 128000),
    ("moonshot-v1-32k", 32000),
    ("moonshot-v1-8k", 8000),
    ("llama-3.1", 131072),
    ("llama3-70b", 8192),
    ("mistral-large", 128000),
    ("mixtral-8x7b", 32768),
]


def lookup_capabilities(model_id: str) -> dict[Capability, Any]:
    """Return aggregated capabilities matched by any rule whose key is a substring."""
    out: dict[Capability, Any] = {}
    mid = model_id.lower()
    for key, caps in _RULES:
        if key in mid:
            for cap, val in caps.items():
                out.setdefault(cap, val)
    return out


def lookup_context_length(model_id: str) -> int | None:
    mid = model_id.lower()
    for key, ctx in _CONTEXT_HINTS:
        if key in mid:
            return ctx
    return None
