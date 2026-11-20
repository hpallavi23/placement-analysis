from sqlalchemy.orm import Session

from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.assessment import Assessment
from app.models.skill import Skill
from app.models.roadmap import RoadmapTask
from app.services.skill_gap import ROLE_REQUIREMENTS, calculate_skill_gap


def get_dashboard_summary(user: User, db: Session) -> dict:
    # 1. Student profile summary (safe handling for missing profile)
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()

    student_summary = {
        "user_id": user.id,
        "email": user.email,
        "full_name": profile.full_name if profile else None,
        "college": profile.college if profile else None,
        "branch": profile.branch if profile else None,
        "graduation_year": profile.graduation_year if profile else None,
        "cgpa": profile.cgpa if profile else None,
    }

    # 2. Latest placement readiness assessment (safe handling for missing assessment)
    latest_assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == user.id)
        .order_by(Assessment.created_at.desc())
        .first()
    )

    if latest_assessment:
        readiness_summary = {
            "has_assessment": True,
            "overall_readiness_score": latest_assessment.readiness_score,
            "aptitude_score": latest_assessment.aptitude_score,
            "technical_score": latest_assessment.technical_score,
            "communication_score": latest_assessment.communication_score,
            "problem_solving_score": latest_assessment.problem_solving_score,
            "last_assessed_at": latest_assessment.created_at,
        }
    else:
        readiness_summary = {
            "has_assessment": False,
            "overall_readiness_score": None,
            "aptitude_score": None,
            "technical_score": None,
            "communication_score": None,
            "problem_solving_score": None,
            "last_assessed_at": None,
        }

    # 3. Skills overview (safe handling for zero skills)
    user_skills = db.query(Skill).filter(Skill.user_id == user.id).all()
    sorted_skills = sorted(user_skills, key=lambda s: s.proficiency, reverse=True)
    top_skills = [
        {"skill_name": s.skill_name, "proficiency": s.proficiency}
        for s in sorted_skills[:5]
    ]

    skills_overview = {
        "total_skills_logged": len(user_skills),
        "top_skills": top_skills,
    }

    # 4. Role readiness across all 5 benchmark roles (reusing calculate_skill_gap)
    role_readiness_list = []
    best_role = None
    highest_readiness = -1.0

    for role_name in ROLE_REQUIREMENTS.keys():
        gap_res = calculate_skill_gap(user_skills, role_name)
        if gap_res:
            pct = gap_res["readiness_percentage"]
            if pct >= 75.0:
                status_label = "Ready"
            elif pct >= 40.0:
                status_label = "In Progress"
            else:
                status_label = "Needs Improvement"

            role_readiness_list.append({
                "role": role_name.title(),
                "readiness_percentage": pct,
                "status": status_label,
            })

            if pct > highest_readiness:
                highest_readiness = pct
                best_role = role_name.title()

    # Sort roles by highest readiness percentage first
    role_readiness_list.sort(key=lambda r: r["readiness_percentage"], reverse=True)

    # 5. Roadmap progress (strictly scoped to user_id)
    roadmap_tasks = (
        db.query(RoadmapTask)
        .filter(RoadmapTask.user_id == user.id)
        .order_by(RoadmapTask.created_at.desc())
        .all()
    )

    if roadmap_tasks:
        # Active role is selected from the most recently created roadmap task
        active_role = roadmap_tasks[0].role
        enrolled_roles = sorted(list({t.role.title() for t in roadmap_tasks}))
        role_tasks = [t for t in roadmap_tasks if t.role == active_role]
        total_tasks = len(role_tasks)
        completed_tasks = sum(1 for t in role_tasks if t.is_completed)
        completion_pct = round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0.0

        pending_high = [
            {
                "id": t.id,
                "skill_name": t.skill_name,
                "current_level": t.current_level,
                "required_level": t.required_level,
                "priority": t.priority,
                "recommendation": t.recommendation,
            }
            for t in role_tasks
            if not t.is_completed and t.priority == "High"
        ]

        roadmap_summary = {
            "has_active_roadmap": True,
            "active_role": active_role.title(),
            "enrolled_roles": enrolled_roles,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_percentage": completion_pct,
            "pending_high_priority_tasks": pending_high,
        }
    else:
        roadmap_summary = {
            "has_active_roadmap": False,
            "active_role": None,
            "enrolled_roles": [],
            "total_tasks": 0,
            "completed_tasks": 0,
            "completion_percentage": 0.0,
            "pending_high_priority_tasks": [],
        }

    # 6. Actionable next recommendation
    if not profile or not profile.cgpa:
        next_action = "Complete your student profile and academic details."
    elif not latest_assessment:
        next_action = "Take the placement readiness assessment to benchmark your skills."
    elif not roadmap_tasks:
        target = best_role or "your preferred role"
        next_action = f"Generate a personalized learning roadmap for {target}."
    elif roadmap_summary["pending_high_priority_tasks"]:
        first_pending = roadmap_summary["pending_high_priority_tasks"][0]
        next_action = f"Complete high-priority roadmap task for {first_pending['skill_name']}."
    elif roadmap_summary["completion_percentage"] < 100.0:
        next_action = "Continue working on remaining roadmap tasks to maximize placement readiness."
    else:
        next_action = "All roadmap tasks completed! Review your readiness and opportunity matches."

    return {
        "student": student_summary,
        "readiness": readiness_summary,
        "skills_overview": skills_overview,
        "role_readiness": role_readiness_list,
        "best_fit_role": best_role,
        "roadmap_progress": roadmap_summary,
        "recommended_next_action": next_action,
    }
