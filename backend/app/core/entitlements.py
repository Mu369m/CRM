"""Centralized plan entitlement decisions for broker infrastructure."""

from dataclasses import dataclass
from enum import StrEnum


class EntitlementKind(StrEnum):
    DATABASE = "DATABASE"
    STORAGE = "STORAGE"


class InfrastructureMode(StrEnum):
    SAAS = "SAAS"
    EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class EntitlementDecision:
    plan: str
    kind: EntitlementKind
    mode: InfrastructureMode
    allowed: bool
    included: bool
    billable: bool
    quota_gb: int | None = None


_PLAN_RULES: dict[
    str, dict[EntitlementKind, dict[InfrastructureMode, EntitlementDecision]]
] = {
    "STARTER": {
        EntitlementKind.DATABASE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "STARTER",
                EntitlementKind.DATABASE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "STARTER",
                EntitlementKind.DATABASE,
                InfrastructureMode.EXTERNAL,
                False,
                False,
                False,
            ),
        },
        EntitlementKind.STORAGE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "STARTER",
                EntitlementKind.STORAGE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
                50,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "STARTER",
                EntitlementKind.STORAGE,
                InfrastructureMode.EXTERNAL,
                False,
                False,
                False,
            ),
        },
    },
    "PROFESSIONAL": {
        EntitlementKind.DATABASE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "PROFESSIONAL",
                EntitlementKind.DATABASE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "PROFESSIONAL",
                EntitlementKind.DATABASE,
                InfrastructureMode.EXTERNAL,
                False,
                False,
                False,
            ),
        },
        EntitlementKind.STORAGE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "PROFESSIONAL",
                EntitlementKind.STORAGE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
                200,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "PROFESSIONAL",
                EntitlementKind.STORAGE,
                InfrastructureMode.EXTERNAL,
                False,
                False,
                False,
            ),
        },
    },
    "ENTERPRISE": {
        EntitlementKind.DATABASE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "ENTERPRISE",
                EntitlementKind.DATABASE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "ENTERPRISE",
                EntitlementKind.DATABASE,
                InfrastructureMode.EXTERNAL,
                True,
                False,
                False,
            ),
        },
        EntitlementKind.STORAGE: {
            InfrastructureMode.SAAS: EntitlementDecision(
                "ENTERPRISE",
                EntitlementKind.STORAGE,
                InfrastructureMode.SAAS,
                True,
                True,
                False,
                500,
            ),
            InfrastructureMode.EXTERNAL: EntitlementDecision(
                "ENTERPRISE",
                EntitlementKind.STORAGE,
                InfrastructureMode.EXTERNAL,
                True,
                False,
                False,
            ),
        },
    },
}


def get_infrastructure_entitlement(
    plan: str, kind: EntitlementKind | str, mode: InfrastructureMode | str
) -> EntitlementDecision:
    """Resolve one authoritative plan/mode decision; unknown plans fail closed."""
    normalized_plan = str(plan).upper()
    normalized_kind = EntitlementKind(kind)
    normalized_mode = InfrastructureMode(mode)
    try:
        return _PLAN_RULES[normalized_plan][normalized_kind][normalized_mode]
    except KeyError:
        return EntitlementDecision(
            normalized_plan,
            normalized_kind,
            normalized_mode,
            False,
            False,
            False,
        )


def is_infrastructure_allowed(
    plan: str, kind: EntitlementKind | str, mode: InfrastructureMode | str
) -> bool:
    return get_infrastructure_entitlement(plan, kind, mode).allowed
