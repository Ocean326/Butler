from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


CAPABILITY_SESSION = "session"
CAPABILITY_RESUME = "resume"
CAPABILITY_COMPACT = "compact"
CAPABILITY_SKILLS = "skills"
CAPABILITY_COLLAB = "collab"
CAPABILITY_SUBAGENT = "subagent"
CAPABILITY_AGENT_TEAM = "agent_team"
CAPABILITY_RECENT_MEMORY = "recent_memory"
CAPABILITY_LOCAL_MEMORY = "local_memory"

KNOWN_CAPABILITIES = (
    CAPABILITY_SESSION,
    CAPABILITY_RESUME,
    CAPABILITY_COMPACT,
    CAPABILITY_SKILLS,
    CAPABILITY_COLLAB,
    CAPABILITY_SUBAGENT,
    CAPABILITY_AGENT_TEAM,
    CAPABILITY_RECENT_MEMORY,
    CAPABILITY_LOCAL_MEMORY,
)


class VendorCapabilityLayer(str, Enum):
    DIRECT_CONTRACT = "direct_contract"
    INTRINSIC = "intrinsic"
    BUTLER_OWNED = "butler_owned"
    UNKNOWN = "unknown"


class VendorCapabilityOwnership(str, Enum):
    VENDOR_NATIVE = "vendor_native"
    BUTLER = "butler"
    HYBRID = "hybrid"


class VendorResumeRecoveryPolicy(str, Enum):
    TRANSPARENT_RESEED = "transparent_reseed"
    EXPLICIT_DEGRADE = "explicit_degrade"
    STRICT_FAIL = "strict_fail"


@dataclass(slots=True, frozen=True)
class VendorCapabilitySpec:
    layer: VendorCapabilityLayer = VendorCapabilityLayer.UNKNOWN
    ownership: VendorCapabilityOwnership = VendorCapabilityOwnership.BUTLER
    notes: str = ""


@dataclass(slots=True)
class VendorCapabilityRegistry:
    vendor_caps: dict[str, dict[str, VendorCapabilitySpec]] = field(default_factory=dict)

    def register_vendor(self, vendor: str, capabilities: Mapping[str, VendorCapabilitySpec]) -> None:
        normalized_vendor = canonical_vendor_name(vendor)
        normalized: dict[str, VendorCapabilitySpec] = {}
        for capability, spec in capabilities.items():
            cap = str(capability or "").strip().lower()
            if not cap:
                continue
            normalized[cap] = spec
        if not normalized:
            return
        self.vendor_caps[normalized_vendor] = normalized

    def get_spec(self, vendor: str, capability: str) -> VendorCapabilitySpec:
        normalized_vendor = canonical_vendor_name(vendor)
        cap = str(capability or "").strip().lower()
        return self.vendor_caps.get(normalized_vendor, {}).get(cap, VendorCapabilitySpec())

    def get_layer(self, vendor: str, capability: str) -> VendorCapabilityLayer:
        return self.get_spec(vendor, capability).layer

    def get_ownership(self, vendor: str, capability: str) -> VendorCapabilityOwnership:
        return self.get_spec(vendor, capability).ownership

    def is_direct_contract(self, vendor: str, capability: str) -> bool:
        return self.get_layer(vendor, capability) == VendorCapabilityLayer.DIRECT_CONTRACT

    def is_intrinsic(self, vendor: str, capability: str) -> bool:
        return self.get_layer(vendor, capability) == VendorCapabilityLayer.INTRINSIC

    def is_butler_owned(self, vendor: str, capability: str) -> bool:
        return self.get_layer(vendor, capability) == VendorCapabilityLayer.BUTLER_OWNED


def canonical_vendor_name(vendor: str | None) -> str:
    token = str(vendor or "").strip().lower()
    if token in {"codex", "codex-cli"}:
        return "codex"
    if token in {"claude", "claude-cli", "anthropic"}:
        return "claude"
    if token in {"cursor", "cursor-cli"}:
        return "cursor"
    return token or "unknown"


def normalize_recovery_policy(
    value: str | None,
    *,
    default: VendorResumeRecoveryPolicy = VendorResumeRecoveryPolicy.TRANSPARENT_RESEED,
) -> VendorResumeRecoveryPolicy:
    token = str(value or "").strip().lower()
    if token in {"transparent", "transparent_reseed", "reseed"}:
        return VendorResumeRecoveryPolicy.TRANSPARENT_RESEED
    if token in {"explicit", "explicit_degrade", "degrade"}:
        return VendorResumeRecoveryPolicy.EXPLICIT_DEGRADE
    if token in {"strict", "strict_fail", "fail"}:
        return VendorResumeRecoveryPolicy.STRICT_FAIL
    return default


def build_default_vendor_registry() -> VendorCapabilityRegistry:
    registry = VendorCapabilityRegistry()
    registry.register_vendor(
        "codex",
        {
            CAPABILITY_SESSION: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.DIRECT_CONTRACT,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_RESUME: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.DIRECT_CONTRACT,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_COMPACT: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_SKILLS: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_COLLAB: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_SUBAGENT: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_AGENT_TEAM: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_RECENT_MEMORY: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.BUTLER_OWNED,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_LOCAL_MEMORY: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.BUTLER_OWNED,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
        },
    )
    registry.register_vendor(
        "claude",
        {
            CAPABILITY_SESSION: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.DIRECT_CONTRACT,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_RESUME: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.DIRECT_CONTRACT,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_COMPACT: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.VENDOR_NATIVE,
            ),
            CAPABILITY_SKILLS: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_COLLAB: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_SUBAGENT: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_AGENT_TEAM: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_RECENT_MEMORY: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
            CAPABILITY_LOCAL_MEMORY: VendorCapabilitySpec(
                layer=VendorCapabilityLayer.INTRINSIC,
                ownership=VendorCapabilityOwnership.BUTLER,
            ),
        },
    )
    return registry


__all__ = [
    "CAPABILITY_AGENT_TEAM",
    "CAPABILITY_COLLAB",
    "CAPABILITY_COMPACT",
    "CAPABILITY_LOCAL_MEMORY",
    "CAPABILITY_RECENT_MEMORY",
    "CAPABILITY_RESUME",
    "CAPABILITY_SESSION",
    "CAPABILITY_SKILLS",
    "CAPABILITY_SUBAGENT",
    "KNOWN_CAPABILITIES",
    "VendorCapabilityLayer",
    "VendorCapabilityOwnership",
    "VendorCapabilityRegistry",
    "VendorCapabilitySpec",
    "VendorResumeRecoveryPolicy",
    "build_default_vendor_registry",
    "canonical_vendor_name",
    "normalize_recovery_policy",
]
