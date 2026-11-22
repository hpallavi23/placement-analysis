from sqlalchemy.orm import object_session
from app.models.assessment import Assessment


ROLE_REQUIREMENTS = {
    "frontend developer": {
        "HTML": 4, "CSS": 4, "JavaScript": 4,
        "React": 3, "Git": 2
    },
    "backend developer": {
        "Python": 4, "SQL": 4, "FastAPI": 3,
        "REST APIs": 4, "Git": 2
    },
    "full stack developer": {
        "HTML": 4, "CSS": 3, "JavaScript": 4,
        "React": 3, "Python": 3, "SQL": 3
    },
    "python developer": {
        "Python": 5, "SQL": 3, "Git": 2,
        "REST APIs": 3, "Problem Solving": 4
    },
    "software development engineer": {
        "Python": 4, "Java": 4, "DSA": 5, "OOP": 4,
        "DBMS": 4, "SQL": 3, "Git": 2, "Problem Solving": 5
    }
}


def convert_problem_solving_score(score: float | None) -> tuple[int, bool]:
    """Convert 0-100 assessment score to (proficiency_level: 0-5, is_assessed: bool)."""
    if score is None:
        return 0, False
    if score == 0.0:
        return 0, True
    if score < 20.0:
        return 1, True
    if score < 40.0:
        return 2, True
    if score < 60.0:
        return 3, True
    if score < 80.0:
        return 4, True
    return 5, True


def get_user_effective_skills(
    user_skills: list,
    latest_assessment=None
) -> tuple[dict[str, int], dict[str, bool]]:
    """Return unified (current_skills_map, is_assessed_map) combining profile skills and assessment scores."""
    current_skills = {
        skill.skill_name.strip().lower(): skill.proficiency
        for skill in user_skills
    }
    is_assessed = {k: True for k in current_skills}

    # Bridge Problem Solving from latest assessment if not directly logged in profile skills
    if "problem solving" not in current_skills:
        score = getattr(latest_assessment, "problem_solving_score", None) if latest_assessment else None
        level, assessed = convert_problem_solving_score(score)
        current_skills["problem solving"] = level
        is_assessed["problem solving"] = assessed

    return current_skills, is_assessed


def calculate_skill_gap(user_skills, role, latest_assessment=None):

    role = role.lower().replace("-", " ").replace("_", " ")

    if role not in ROLE_REQUIREMENTS:
        return None

    requirements = ROLE_REQUIREMENTS[role]

    # Resolve session-attached latest_assessment if not explicitly passed
    if latest_assessment is None and user_skills:
        try:
            first_item = user_skills[0]
            session = object_session(first_item)
            user_id = getattr(first_item, "user_id", None)
            if session and user_id is not None:
                latest_assessment = (
                    session.query(Assessment)
                    .filter(Assessment.user_id == user_id)
                    .order_by(Assessment.created_at.desc())
                    .first()
                )
        except Exception:
            pass

    current_skills, is_assessed_map = get_user_effective_skills(user_skills, latest_assessment)

    results = []
    total_required = 0
    total_achieved = 0

    for skill, required in requirements.items():
        skill_key = skill.lower()
        current = current_skills.get(skill_key, 0)
        is_assessed = is_assessed_map.get(skill_key, False)
        gap = max(required - current, 0)

        total_required += required
        total_achieved += min(current, required)

        if not is_assessed:
            status = "Unassessed"
        elif current == 0:
            status = "Needs Improvement"
        elif current < required:
            status = "Needs Improvement"
        else:
            status = "Ready"

        results.append({
            "skill": skill,
            "current_level": current,
            "required_level": required,
            "gap": gap,
            "status": status,
            "is_assessed": is_assessed
        })

    readiness = round((total_achieved / total_required) * 100, 2)

    return {
        "role": role.title(),
        "readiness_percentage": readiness,
        "skills": results
    }