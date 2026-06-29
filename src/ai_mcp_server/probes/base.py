"""Probe primitives shared by all capability probes."""
from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import Any

from ..models.enums import Capability, ProbeStatus
from ..models.schemas import InvokeResult, ProbeResult
from ..providers.base import ProviderAdapter
from ..utils.path_util import probe_assets_dir


def classify(invoke: InvokeResult) -> ProbeStatus:
    """Map an InvokeResult to a probe status."""
    if invoke.error is None and invoke.ok:
        return ProbeStatus.OK
    if invoke.error and invoke.error.get("type") == "timeout":
        return ProbeStatus.TIMEOUT
    status = invoke.upstream_status
    if status == 429:
        return ProbeStatus.RATE_LIMITED
    if 500 <= status < 600:
        return ProbeStatus.ERROR
    if 400 <= status < 500:
        return ProbeStatus.NOT_SUPPORTED
    return ProbeStatus.ERROR


def make_result(
    capability: Capability,
    invoke: InvokeResult,
    structural_ok: Callable[[Any], bool] | None = None,
) -> ProbeResult:
    """Combine HTTP status + optional structural check into a ProbeResult."""
    status = classify(invoke)
    if status is ProbeStatus.OK and structural_ok is not None:
        if not structural_ok(invoke.body):
            status = ProbeStatus.NOT_SUPPORTED
    ok = status is ProbeStatus.OK
    err: str | None = None
    if invoke.error:
        err = str(invoke.error)
    return ProbeResult(
        capability=capability,
        status=status,
        ok=ok,
        latency_ms=invoke.latency_ms,
        raw={"upstream_status": invoke.upstream_status, "body": invoke.body},
        error=err,
    )


def load_digit_image_b64() -> str | None:
    """Return base64-encoded digit_1.png if it exists."""
    p = probe_assets_dir() / "digit_1.png"
    if not p.exists():
        return None
    return base64.b64encode(p.read_bytes()).decode("ascii")


def load_digit_audio_bytes() -> tuple[bytes, str] | None:
    """Return (wav_bytes, filename). None if asset missing."""
    p = probe_assets_dir() / "digit_1.wav"
    if not p.exists():
        return None
    return p.read_bytes(), p.name


def skipped(capability: Capability, reason: str) -> ProbeResult:
    return ProbeResult(
        capability=capability,
        status=ProbeStatus.SKIPPED,
        ok=False,
        latency_ms=0,
        error=reason,
    )


# Type alias for probe functions
ProbeFn = Callable[[ProviderAdapter, str], Awaitable[ProbeResult]]
