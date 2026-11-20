"""NXTSTEP Evidence-Aware Scoring Service.

Rules:
- E0: No skill claim exists (has_skill=False). Weight λ = 0.0.
- E1: Skill is self-reported but has no approved evidence. Weight λ = 0.5.
- E2: At least one submitted evidence item has been approved. Weight λ = 1.0.
- Pending and rejected evidence do not increase the tier.
- Multiple submissions: one approved item is sufficient for E2.
- Adjusted proficiency = round(reported proficiency × λ, 2).
- Backend authority: tiers and multipliers are calculated dynamically from verified records,
  never from client-supplied inputs.
"""

from typing import Any, Mapping, Sequence

TIER_E0 = "E0"
TIER_E1 = "E1"
TIER_E2 = "E2"

LAMBDA_WEIGHTS: dict[str, float] = {
    TIER_E0: 0.0,
    TIER_E1: 0.5,
    TIER_E2: 1.0,
}

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


def _extract_item_status(item: Any) -> str:
    """Helper to safely extract the status string from an ORM model or mapping."""
    if isinstance(item, Mapping):
        return str(item.get("status", "")).strip().lower()
    return str(getattr(item, "status", "")).strip().lower()


def determine_evidence_tier(
    evidence_items: Sequence[Any] | None,
    has_skill: bool = True
) -> tuple[str, float]:
    """Determine the evidence tier (E0, E1, E2) and lambda weight (0.0, 0.5, 1.0).

    Args:
        evidence_items: Sequence of SkillEvidence records or dicts.
        has_skill: Boolean indicating whether an underlying skill record exists.

    Returns:
        tuple[str, float]: (tier_name, lambda_weight)
    """
    if not has_skill:
        return TIER_E0, LAMBDA_WEIGHTS[TIER_E0]

    if evidence_items:
        for item in evidence_items:
            if _extract_item_status(item) == STATUS_APPROVED:
                return TIER_E2, LAMBDA_WEIGHTS[TIER_E2]

    return TIER_E1, LAMBDA_WEIGHTS[TIER_E1]


def calculate_adjusted_proficiency(
    reported_proficiency: int | float | None,
    lambda_weight: float
) -> float:
    """Calculate the evidence-adjusted proficiency: round(reported_proficiency * lambda, 2).

    Clamps negative values to 0.0.
    """
    if reported_proficiency is None:
        return 0.0
    safe_reported = max(0.0, float(reported_proficiency))
    safe_lambda = max(0.0, float(lambda_weight))
    return round(safe_reported * safe_lambda, 2)


def score_skill_evidence(
    reported_proficiency: int | float | None,
    evidence_items: Sequence[Any] | None = None,
    has_skill: bool = True
) -> dict[str, Any]:
    """Compute complete evidence scoring breakdown for a skill.

    Returns:
        dict with:
        - evidence_level: "E0" | "E1" | "E2"
        - lambda_weight: 0.0 | 0.5 | 1.0
        - reported_proficiency: int (0 if no skill)
        - adjusted_proficiency: float
        - evidence_counts: dict of { total, approved, pending, rejected }
    """
    tier, lambda_weight = determine_evidence_tier(
        evidence_items=evidence_items,
        has_skill=has_skill
    )

    reported = int(reported_proficiency) if (has_skill and reported_proficiency is not None) else 0
    adjusted = calculate_adjusted_proficiency(reported, lambda_weight)

    items = evidence_items or []
    counts = {
        "total": len(items),
        "approved": sum(1 for e in items if _extract_item_status(e) == STATUS_APPROVED),
        "pending": sum(1 for e in items if _extract_item_status(e) == STATUS_PENDING),
        "rejected": sum(1 for e in items if _extract_item_status(e) == STATUS_REJECTED),
    }

    return {
        "evidence_level": tier,
        "lambda_weight": lambda_weight,
        "reported_proficiency": reported,
        "adjusted_proficiency": adjusted,
        "evidence_counts": counts,
    }
