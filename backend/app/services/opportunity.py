"""Placement Opportunity Analysis Service (Rule-Based).

This module provides rule-based matching against illustrative benchmark campus
opportunities to help students evaluate placement readiness.

IMPORTANT:
- Company names, packages, cutoffs, and job descriptions are illustrative benchmark
  profiles for academic self-assessment, not verified live recruitment postings.
- Overall fit scores are deterministic rule-based heuristics, NOT placement
  probabilities or machine learning predictions.
"""

from typing import Any
from app.models.skill import Skill

BENCHMARK_DISCLAIMER = (
    "Illustrative benchmark opportunity for readiness analysis; "
    "not verified live recruitment data."
)

BENCHMARK_OPPORTUNITIES = [
    {
        "id": 1,
        "company_name": "TCS (Illustrative Benchmark)",
        "role_title": "Digital Software Engineer",
        "package_lpa": 7.5,
        "min_cgpa": 7.0,
        "location": "Pan India (Illustrative)",
        "description": "Benchmark role focusing on cloud-native apps, databases, and microservices.",
        "required_skills": {
            "Python": 3,
            "SQL": 3,
            "DSA": 3,
            "Git": 2
        }
    },
    {
        "id": 2,
        "company_name": "Infosys (Illustrative Benchmark)",
        "role_title": "Specialist Programmer",
        "package_lpa": 9.5,
        "min_cgpa": 7.0,
        "location": "Bangalore / Pune / Hyderabad (Illustrative)",
        "description": "Benchmark cohort role working on core algorithmic problems and system architecture.",
        "required_skills": {
            "Python": 4,
            "DSA": 4,
            "SQL": 3,
            "Problem Solving": 4
        }
    },
    {
        "id": 3,
        "company_name": "Amazon (Illustrative Benchmark)",
        "role_title": "Software Development Engineer (SDE-1)",
        "package_lpa": 24.0,
        "min_cgpa": 7.5,
        "location": "Bangalore / Hyderabad (Illustrative)",
        "description": "Benchmark role building high-scale distributed systems and cloud architectures.",
        "required_skills": {
            "DSA": 5,
            "Problem Solving": 5,
            "Python": 4,
            "OOP": 4,
            "SQL": 3
        }
    },
    {
        "id": 4,
        "company_name": "Cognizant (Illustrative Benchmark)",
        "role_title": "GenC Next Developer",
        "package_lpa": 6.75,
        "min_cgpa": 6.5,
        "location": "Chennai / Bangalore (Illustrative)",
        "description": "Benchmark role focusing on modern API development and backend service integration.",
        "required_skills": {
            "Python": 3,
            "SQL": 3,
            "Git": 2,
            "REST APIs": 3
        }
    },
    {
        "id": 5,
        "company_name": "Accenture (Illustrative Benchmark)",
        "role_title": "Advanced Application Engineering Analyst",
        "package_lpa": 6.5,
        "min_cgpa": 6.5,
        "location": "Bangalore / Gurgaon (Illustrative)",
        "description": "Benchmark full lifecycle enterprise engineering across backend services and CI/CD.",
        "required_skills": {
            "Python": 3,
            "SQL": 3,
            "Git": 2,
            "REST APIs": 3
        }
    },
    {
        "id": 6,
        "company_name": "Thoughtworks (Illustrative Benchmark)",
        "role_title": "Full Stack Developer",
        "package_lpa": 11.0,
        "min_cgpa": 7.0,
        "location": "Bangalore / Pune (Illustrative)",
        "description": "Benchmark role driving end-to-end full stack web platforms and agile development.",
        "required_skills": {
            "HTML": 4,
            "JavaScript": 4,
            "React": 3,
            "Python": 3,
            "SQL": 3
        }
    },
    {
        "id": 7,
        "company_name": "Tech Mahindra (Illustrative Benchmark)",
        "role_title": "Backend Developer",
        "package_lpa": 5.5,
        "min_cgpa": 6.0,
        "location": "Hyderabad / Noida (Illustrative)",
        "description": "Benchmark role designing and maintaining robust RESTful APIs and database schemas.",
        "required_skills": {
            "Python": 3,
            "SQL": 3,
            "FastAPI": 2,
            "REST APIs": 3
        }
    },
    {
        "id": 8,
        "company_name": "Wipro (Illustrative Benchmark)",
        "role_title": "Turbo Frontend Developer",
        "package_lpa": 6.5,
        "min_cgpa": 6.5,
        "location": "Bangalore / Chennai (Illustrative)",
        "description": "Benchmark role creating responsive, accessible user interfaces and modern web applications.",
        "required_skills": {
            "HTML": 4,
            "CSS": 4,
            "JavaScript": 3,
            "React": 3
        }
    }
]


def evaluate_opportunity_match(
    opp: dict[str, Any],
    user_cgpa: float | None,
    user_skills_map: dict[str, int]
) -> dict[str, Any]:
    """Evaluate a single opportunity match using transparent rule-based heuristics."""
    min_cgpa = float(opp.get("min_cgpa", 0.0))

    # 1. CGPA eligibility states (three distinct states)
    if user_cgpa is None:
        cgpa_status = "Unknown (CGPA not provided)"
        is_eligible_cgpa = None
    elif user_cgpa >= min_cgpa:
        cgpa_status = "Eligible"
        is_eligible_cgpa = True
    else:
        cgpa_status = "Not Eligible"
        is_eligible_cgpa = False

    # 2. Skill matching with zero-default and negative clamping
    required_skills_dict = opp.get("required_skills", {})
    total_required = 0
    total_achieved = 0
    missing_skills: list[dict[str, Any]] = []
    seen_skills: set[str] = set()

    for skill_name, required_level in required_skills_dict.items():
        norm_name = str(skill_name).strip().lower()
        if not norm_name or norm_name in seen_skills:
            continue
        seen_skills.add(norm_name)

        req_level = max(0, int(required_level))
        raw_user_level = user_skills_map.get(norm_name, 0)
        current_level = max(0, int(raw_user_level))

        gap = max(req_level - current_level, 0)
        achieved = min(current_level, req_level)

        total_required += req_level
        total_achieved += achieved

        if gap > 0:
            missing_skills.append({
                "skill": str(skill_name).strip(),
                "current_level": current_level,
                "required_level": req_level,
                "gap": gap
            })

    # Empty required skills dict safely yields 0.0 match
    if total_required > 0:
        skill_match = round((total_achieved / total_required) * 100.0, 2)
    else:
        skill_match = 0.0

    # 3. Overall fit score & status (strictly rule-based heuristic)
    if cgpa_status == "Eligible":
        cgpa_score = min(max(user_cgpa, 0.0) / 10.0 * 100.0, 100.0)
        overall_fit = round(0.30 * cgpa_score + 0.70 * skill_match, 2)
        if skill_match >= 75.0:
            status = "Eligible & High Match"
        elif skill_match >= 50.0:
            status = "Eligible - Moderate Match"
        else:
            status = "Eligible - Significant Skill Gap"

    elif cgpa_status == "Not Eligible":
        # Scaled down heuristic (50% of demonstrated skill match)
        overall_fit = round(0.50 * skill_match, 2)
        status = "Not Eligible - CGPA Below Cutoff"

    else:
        # Unknown CGPA: 100% of demonstrated skill match without academic penalty
        overall_fit = round(skill_match, 2)
        if skill_match >= 75.0:
            status = "High Skill Match (CGPA Verification Required)"
        elif skill_match >= 50.0:
            status = "Moderate Skill Match (CGPA Verification Required)"
        else:
            status = "Skill Gap (CGPA Verification Required)"

    return {
        "id": int(opp.get("id", 0)),
        "company_name": str(opp.get("company_name", "Unknown")),
        "role_title": str(opp.get("role_title", "Unknown")),
        "package_lpa": float(opp.get("package_lpa", 0.0)),
        "min_cgpa": min_cgpa,
        "location": str(opp.get("location", "Not specified")),
        "description": opp.get("description"),
        "required_skills": required_skills_dict,
        "cgpa_eligibility_status": cgpa_status,
        "is_eligible_cgpa": is_eligible_cgpa,
        "skill_match_percentage": skill_match,
        "overall_fit_score": overall_fit,
        "score_type": "rule_based_heuristic",
        "status": status,
        "missing_skills": missing_skills,
        "benchmark_disclaimer": BENCHMARK_DISCLAIMER
    }


def _extract_skills_map(user_skills: list[Any]) -> dict[str, int]:
    """Helper to convert skills list (ORM objects or dicts) into a normalized map."""
    skills_map: dict[str, int] = {}
    for s in user_skills:
        if isinstance(s, dict):
            name = s.get("skill_name", "")
            prof = s.get("proficiency", 0)
        else:
            name = getattr(s, "skill_name", "")
            prof = getattr(s, "proficiency", 0)

        cleaned_name = str(name).strip().lower()
        if cleaned_name:
            skills_map[cleaned_name] = max(0, int(prof))
    return skills_map


def get_all_opportunity_matches(
    user_cgpa: float | None,
    user_skills: list[Any]
) -> list[dict[str, Any]]:
    """Return all benchmark opportunity matches sorted by overall_fit_score descending."""
    skills_map = _extract_skills_map(user_skills)
    results = [
        evaluate_opportunity_match(opp, user_cgpa, skills_map)
        for opp in BENCHMARK_OPPORTUNITIES
    ]
    # Sort opportunities: highest overall fit score first
    results.sort(key=lambda x: x["overall_fit_score"], reverse=True)
    return results


def get_opportunity_match_by_id(
    opportunity_id: int,
    user_cgpa: float | None,
    user_skills: list[Any]
) -> dict[str, Any] | None:
    """Return match details for a specific benchmark opportunity or None if not found."""
    opp = next((o for o in BENCHMARK_OPPORTUNITIES if o.get("id") == opportunity_id), None)
    if not opp:
        return None
    skills_map = _extract_skills_map(user_skills)
    return evaluate_opportunity_match(opp, user_cgpa, skills_map)
