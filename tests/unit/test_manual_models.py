import pytest

from ai_mcp_server.application import endpoint_service, manual_models
from ai_mcp_server.capability import resolver
from ai_mcp_server.models.enums import Capability
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


def test_add_models_registers_models_without_discovery():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")

    result = manual_models.add_models(
        "nv",
        ["custom-model-a", "custom-model-b"],
        context_length=8000,
        capabilities=[Capability.TEXT_CHAT, Capability.TOOL_CALL],
    )

    assert result["count"] == 2
    with connect() as conn:
        models = {m.model_id: m for m in dao.list_models(conn, endpoint_id=ep.id)}
        assert set(models) == {"custom-model-a", "custom-model-b"}
        assert models["custom-model-a"].context_length == 8000
        caps = resolver.resolve(conn, models["custom-model-a"])
    assert caps[Capability.TEXT_CHAT].value is True
    assert caps[Capability.TOOL_CALL].value is True


def test_add_models_registers_feature_overrides_with_aliases():
    ep = endpoint_service.add_endpoint("volc", "https://example.com/v1", "sk")

    result = manual_models.add_models(
        "volc",
        ["seed-tts-2.0", "volc.seedasr.sauc.duration"],
        feature_overrides={"tts": True, "asr": False, "ctx": 32000},
    )

    assert result["features"] == {
        "audio_tts": True,
        "audio_stt": False,
        "context_length": 32000,
    }
    with connect() as conn:
        tts_model = dao.get_model(conn, ep.id, "seed-tts-2.0")
        assert tts_model is not None
        caps = resolver.resolve(conn, tts_model)
        ctx, ctx_source = resolver.resolve_context_length(conn, tts_model)
    assert caps[Capability.AUDIO_TTS].value is True
    assert caps[Capability.AUDIO_STT].value is False
    assert ctx == 32000
    assert ctx_source is not None


def test_add_models_unknown_endpoint_returns_error():
    result = manual_models.add_models("missing", ["m"])
    assert "error" in result


def test_add_models_requires_at_least_one_id():
    endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    result = manual_models.add_models("nv", ["   "])
    assert "error" in result


def test_remove_model():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    manual_models.add_models("nv", ["m1"])

    removed = manual_models.remove_model("nv", "m1")
    assert removed["removed"] is True

    with connect() as conn:
        assert dao.get_model(conn, ep.id, "m1") is None

    missing = manual_models.remove_model("nv", "nope")
    assert missing["removed"] is False


def test_remove_model_also_clears_overrides():
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    manual_models.add_models("nv", ["m2"], capabilities=[Capability.TEXT_CHAT])

    with connect() as conn:
        assert dao.list_overrides(conn, ep.id, "m2")

    manual_models.remove_model("nv", "m2")

    with connect() as conn:
        assert dao.list_overrides(conn, ep.id, "m2") == {}


def test_parse_capabilities():
    assert manual_models.parse_capabilities(None) is None
    assert manual_models.parse_capabilities(" text_chat , vision , asr ") == [
        Capability.TEXT_CHAT,
        Capability.VISION,
        Capability.AUDIO_STT,
    ]
    with pytest.raises(ValueError):
        manual_models.parse_capabilities("not-a-cap")


def test_parse_feature_overrides():
    assert manual_models.parse_feature_overrides("tts=true,asr=false,ctx=16000") == {
        "audio_tts": True,
        "audio_stt": False,
        "context_length": 16000,
    }
    assert manual_models.parse_feature_overrides("vision") == {"vision": True}
    with pytest.raises(ValueError):
        manual_models.parse_feature_overrides("audio_tts=maybe")
