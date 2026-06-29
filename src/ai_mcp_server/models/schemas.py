"""DTOs and shared dataclasses crossing layer boundaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import Capability, CapabilitySource, JobStatus, ProbeStatus, ProviderType


@dataclass(slots=True)
class EndpointDTO:
    id: int
    name: str
    base_url: str
    provider_type: ProviderType
    created_at: str
    updated_at: str


@dataclass(slots=True)
class CapabilityValue:
    """One capability resolution result. value can be bool or int or str."""

    value: Any
    source: CapabilitySource
    probed_at: str | None = None


@dataclass(slots=True)
class ModelDTO:
    endpoint_id: int
    endpoint_name: str
    model_id: str
    capabilities: dict[str, CapabilityValue]
    context_length: int | None
    raw_meta: dict[str, Any] | None
    performance: dict[str, Any]
    last_discovered_at: str

    @property
    def full_id(self) -> str:
        return f"{self.endpoint_name}/{self.model_id}"


@dataclass(slots=True)
class ProbeResult:
    capability: Capability
    status: ProbeStatus
    ok: bool
    latency_ms: int
    raw: dict[str, Any] | None = None
    error: str | None = None


@dataclass(slots=True)
class ProbeJobDTO:
    id: int
    endpoint_id: int
    model_id: str
    capability: Capability
    status: JobStatus
    priority: int
    claimed_by: str | None
    claimed_at: str | None
    lease_until: str | None
    finished_at: str | None
    error: str | None
    created_at: str


@dataclass(slots=True)
class InvokeResult:
    """Result of provider invocation. Either body or error is set."""

    upstream_status: int
    body: Any
    latency_ms: int
    error: dict[str, Any] | None = field(default=None)
    first_byte_ms: int | None = field(default=None)

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.upstream_status < 300
