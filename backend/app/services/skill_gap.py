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
        "Python": 4, "DSA": 5, "OOP": 4,
        "SQL": 3, "Git": 2, "Problem Solving": 5
    }
}


def calculate_skill_gap(user_skills, role):

    role = role.lower().replace("-", " ").replace("_", " ")

    if role not in ROLE_REQUIREMENTS:
        return None

    requirements = ROLE_REQUIREMENTS[role]

    current_skills = {
        skill.skill_name.strip().lower(): skill.proficiency
        for skill in user_skills
    }

    results = []
    total_required = 0
    total_achieved = 0

    for skill, required in requirements.items():

        current = current_skills.get(skill.lower(), 0)
        gap = max(required - current, 0)

        total_required += required
        total_achieved += min(current, required)

        if current == 0:
            status = "Missing"
        elif current < required:
            status = "Needs Improvement"
        else:
            status = "Ready"

        results.append({
            "skill": skill,
            "current_level": current,
            "required_level": required,
            "gap": gap,
            "status": status
        })

    readiness = round((total_achieved / total_required) * 100, 2)

    return {
        "role": role.title(),
        "readiness_percentage": readiness,
        "skills": results
    }