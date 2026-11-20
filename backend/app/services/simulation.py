"""What-If Simulation Service (Rule-Based, Non-Destructive).

Enables students to explore hypothetical improvements (e.g. higher CGPA,
increased skill proficiencies, or improved assessment scores) and observe
the simulated impact on placement readiness, role competency, and benchmark
company eligibility.

IMPORTANT:
- Operates 100% in-memory; never writes to, modifies, or deletes database records.
- Deterministic rule-based heuristic for academic planning; not machine learning
  or guaranteed placement outcomes.
"""

from collections import namedtuple
from sqlalchemy.orm import Session

from app.models.student_profile import StudentProfile
from app.models.assessment import Assessment
from app.models.skill import Skill
from app.services.readiness import calculate_readiness_score
from app.services.skill_gap import ROLE_REQUIREMENTS, calculate_skill_gap
from app.services.opportunity import (
    BENCHMARK_OPPORTUNITIES,
    evaluate_opportunity_match
)
from app.schemas.simulation import WhatIfRequest

SimpleSkill = namedtuple("SimpleSkill", ["skill_name", "proficiency"])


def run_what_if_simulation(
    user_id: int,
    request: WhatIfRequest,
    db: Session
) -> dict:
    # 1. Load current baseline data for authenticated user
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user_id
    ).first()
    current_cgpa = profile.cgpa if profile else None

    latest_assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == user_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )

    skills = db.query(Skill).filter(Skill.user_id == user_id).all()
    current_skills_map = {
        s.skill_name.strip().lower(): s.proficiency
        for s in skills
    }

    # 2. Assessment readiness score simulation
    if latest_assessment:
        curr_apt = latest_assessment.aptitude_score
        curr_tech = latest_assessment.technical_score
        curr_comm = latest_assessment.communication_score
        curr_prob = latest_assessment.problem_solving_score
        curr_readiness = latest_assessment.readiness_score
    else:
        curr_apt = None
        curr_tech = None
        curr_comm = None
        curr_prob = None
        curr_readiness = None

    # Merge simulated overrides
    has_sim_assessment = any(
        v is not None for v in [
            request.simulated_aptitude,
            request.simulated_technical,
            request.simulated_communication,
            request.simulated_problem_solving
        ]
    )

    if has_sim_assessment or curr_readiness is not None:
        sim_apt = request.simulated_aptitude if request.simulated_aptitude is not None else (curr_apt or 0.0)
        sim_tech = request.simulated_technical if request.simulated_technical is not None else (curr_tech or 0.0)
        sim_comm = request.simulated_communication if request.simulated_communication is not None else (curr_comm or 0.0)
        sim_prob = request.simulated_problem_solving if request.simulated_problem_solving is not None else (curr_prob or 0.0)
        sim_readiness = calculate_readiness_score(sim_apt, sim_tech, sim_comm, sim_prob)
        readiness_delta = round(sim_readiness - curr_readiness, 2) if curr_readiness is not None else None
        readiness_comparison = {
            "current": curr_readiness,
            "simulated": sim_readiness,
            "delta": readiness_delta
        }
    else:
        readiness_comparison = None

    # 3. Skills map simulation (clamp proficiencies between 0 and 5)
    simulated_skills_map = current_skills_map.copy()
    if request.simulated_skills:
        for sk_name, lvl in request.simulated_skills.items():
            clamped = max(0, min(5, int(lvl)))
            simulated_skills_map[sk_name.strip().lower()] = clamped

    # 4. CGPA simulation
    simulated_cgpa = (
        request.simulated_cgpa
        if request.simulated_cgpa is not None
        else current_cgpa
    )

    # 5. Role readiness comparisons across all 5 benchmark roles
    current_skill_objs = [
        SimpleSkill(skill_name=k, proficiency=v)
        for k, v in current_skills_map.items()
    ]
    sim_skill_objs = [
        SimpleSkill(skill_name=k, proficiency=v)
        for k, v in simulated_skills_map.items()
    ]

    all_roles_readiness = []
    target_role_comparison = None
    target_role_clean = (
        request.target_role.lower().replace("-", " ").replace("_", " ").strip()
        if request.target_role
        else None
    )

    for role_name in ROLE_REQUIREMENTS.keys():
        curr_gap = calculate_skill_gap(current_skill_objs, role_name)
        sim_gap = calculate_skill_gap(sim_skill_objs, role_name)

        c_pct = curr_gap["readiness_percentage"] if curr_gap else 0.0
        s_pct = sim_gap["readiness_percentage"] if sim_gap else 0.0
        delta = round(s_pct - c_pct, 2)

        def _get_status(pct: float) -> str:
            if pct >= 75.0:
                return "Ready"
            if pct >= 40.0:
                return "In Progress"
            return "Needs Improvement"

        item = {
            "role": role_name.title(),
            "current_readiness": c_pct,
            "simulated_readiness": s_pct,
            "delta": delta,
            "status_before": _get_status(c_pct),
            "status_after": _get_status(s_pct)
        }
        all_roles_readiness.append(item)

        if target_role_clean and role_name == target_role_clean:
            target_role_comparison = {
                "current": c_pct,
                "simulated": s_pct,
                "delta": delta
            }

    # Sort roles by simulated readiness descending
    all_roles_readiness.sort(key=lambda r: r["simulated_readiness"], reverse=True)

    # 6. Opportunity impact simulation
    curr_matches = [
        evaluate_opportunity_match(opp, current_cgpa, current_skills_map)
        for opp in BENCHMARK_OPPORTUNITIES
    ]
    sim_matches = [
        evaluate_opportunity_match(opp, simulated_cgpa, simulated_skills_map)
        for opp in BENCHMARK_OPPORTUNITIES
    ]

    curr_eligible_count = sum(
        1 for m in curr_matches if m["cgpa_eligibility_status"] == "Eligible"
    )
    sim_eligible_count = sum(
        1 for m in sim_matches if m["cgpa_eligibility_status"] == "Eligible"
    )

    # Qualified is defined as eligible CGPA AND at least 50% skill match
    curr_qualified_ids = {
        m["id"] for m in curr_matches
        if m["cgpa_eligibility_status"] == "Eligible" and m["skill_match_percentage"] >= 50.0
    }
    sim_qualified_ids = {
        m["id"] for m in sim_matches
        if m["cgpa_eligibility_status"] == "Eligible" and m["skill_match_percentage"] >= 50.0
    }

    newly_unlocked_ids = sim_qualified_ids - curr_qualified_ids
    newly_unlocked_companies = [
        m["company_name"] for m in sim_matches
        if m["id"] in newly_unlocked_ids
    ]

    avg_fit_before = round(
        sum(m["overall_fit_score"] for m in curr_matches) / len(curr_matches), 2
    )
    avg_fit_after = round(
        sum(m["overall_fit_score"] for m in sim_matches) / len(sim_matches), 2
    )

    opportunities_impact = {
        "current_eligible_count": curr_eligible_count,
        "simulated_eligible_count": sim_eligible_count,
        "newly_unlocked_companies": newly_unlocked_companies,
        "average_fit_score_before": avg_fit_before,
        "average_fit_score_after": avg_fit_after
    }

    # 7. Synthesize actionable, human-readable insights
    insights = []
    if newly_unlocked_companies:
        insights.append(
            f"Simulated improvements unlock qualification for {len(newly_unlocked_companies)} "
            f"new benchmark opportunity(ies): {', '.join(newly_unlocked_companies)}."
        )

    if readiness_comparison and readiness_comparison["delta"]:
        sign = "+" if readiness_comparison["delta"] > 0 else ""
        insights.append(
            f"Placement assessment score shifts from {readiness_comparison['current']} "
            f"to {readiness_comparison['simulated']} ({sign}{readiness_comparison['delta']}%)."
        )

    # Highest growth role
    max_growth_role = max(all_roles_readiness, key=lambda r: r["delta"])
    if max_growth_role["delta"] > 0:
        insights.append(
            f"Strongest skill boost in {max_growth_role['role']}: "
            f"+{max_growth_role['delta']}% readiness improvement "
            f"(from {max_growth_role['current_readiness']}% to {max_growth_role['simulated_readiness']}%)."
        )

    if simulated_cgpa and current_cgpa and simulated_cgpa > current_cgpa:
        insights.append(
            f"Raising CGPA to {simulated_cgpa} elevates academic standing across all "
            f"benchmark campus recruitment drives with GPA cutoffs."
        )

    if not insights:
        insights.append(
            "No parameter differences detected. Adjust CGPA, skill proficiencies, "
            "or assessment scores to simulate projected growth."
        )

    return {
        "readiness_score": readiness_comparison,
        "target_role": request.target_role,
        "target_role_readiness": target_role_comparison,
        "all_roles_readiness": all_roles_readiness,
        "opportunities_impact": opportunities_impact,
        "insights": insights,
        "simulation_disclaimer": (
            "Illustrative rule-based simulation heuristic for planning; "
            "does not guarantee hiring outcomes."
        )
    }
