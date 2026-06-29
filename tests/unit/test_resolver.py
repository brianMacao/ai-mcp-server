from ai_mcp_server.application import endpoint_service, override_service
from ai_mcp_server.capability import static_map
from ai_mcp_server.capability.resolver import resolve
from ai_mcp_server.models.enums import Capability, CapabilitySource
from ai_mcp_server.storage import dao
from ai_mcp_server.storage.db import connect


def test_static_lookup_gpt4o():
    caps = static_map.lookup_capabilities("openai/gpt-4o")
    assert Capability.VISION in caps
    assert Capability.TOOL_CALL in caps
    assert Capability.TEXT_CHAT in caps


def test_static_lookup_doubao_seedream_image_gen():
    caps = static_map.lookup_capabilities("doubao-seedream-5.0-lite")

    assert caps == {Capability.IMAGE_GEN: True}


def test_static_lookup_volc_audio_models():
    assert static_map.lookup_capabilities("seed-tts-2.0") == {
        Capability.AUDIO_TTS: True
    }
    assert static_map.lookup_capabilities("volc.seedasr.sauc.duration") == {
        Capability.AUDIO_STT: True
    }


def test_priority_override_beats_probe():
    """user override > probe > litellm > static."""
    ep = endpoint_service.add_endpoint("nv", "https://example.com/v1", "sk")
    with connect() as conn:
        dao.upsert_model(conn, ep.id, "gpt-4o")
        # Probe says vision=False (would override static)
        dao.update_model_capability(
            conn, ep.id, "gpt-4o", "vision", False,
            CapabilitySource.PROBE, probed_at="2025-01-01",
        )
        m = dao.get_model(conn, ep.id, "gpt-4o")
        caps = resolve(conn, m)
    # probe wins over static
    assert caps[Capability.VISION].source == CapabilitySource.PROBE
    assert caps[Capability.VISION].value is False

    # Now user override wins over probe
    override_service.set_override("nv", "gpt-4o", "vision", True)
    with connect() as conn:
        m = dao.get_model(conn, ep.id, "gpt-4o")
        caps = resolve(conn, m)
    assert caps[Capability.VISION].source == CapabilitySource.OVERRIDE
    assert caps[Capability.VISION].value is True
