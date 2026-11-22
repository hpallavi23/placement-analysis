from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.skill import Skill
from app.models.assessment import Assessment
from app.models.roadmap import RoadmapTask

from app.schemas.roadmap import RoadmapTaskResponse, RoadmapTaskCompleteResponse

from app.api.v1.endpoints.auth import get_current_user

from app.services.skill_gap import (
    ROLE_REQUIREMENTS,
    get_user_effective_skills
)
from app.services.roadmap import (
    generate_recommendation,
    get_priority
)


router = APIRouter(prefix="/roadmaps", tags=["Learning Roadmap"])


# Generate a personalized roadmap
@router.post("/{role}/generate", response_model=list[RoadmapTaskResponse])
def create_roadmap(
    role: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    role = role.lower().replace("-", " ").replace("_", " ").strip()

    requirements = ROLE_REQUIREMENTS.get(role)

    if not requirements:
        raise HTTPException(status_code=404, detail="Role not supported")

    skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()

    latest_assessment = db.query(Assessment).filter(
        Assessment.user_id == user.id
    ).order_by(Assessment.created_at.desc()).first()

    current_skills, is_assessed_map = get_user_effective_skills(skills, latest_assessment)

    existing_tasks = db.query(RoadmapTask).filter(
        RoadmapTask.user_id == user.id,
        RoadmapTask.role == role
    ).all()

    task_map = {task.skill_name: task for task in existing_tasks}

    for skill, required in requirements.items():
        skill_key = skill.lower()
        current = current_skills.get(skill_key, 0)
        is_assessed = is_assessed_map.get(skill_key, False)
        task = task_map.get(skill)

        if current >= required:
            if task:
                db.delete(task)
            continue

        if not is_assessed:
            if skill.lower() == "problem solving":
                recommendation = (
                    f"Complete your Placement Readiness Assessment to evaluate your "
                    f"Problem Solving proficiency. Target level: {required}/5."
                )
            else:
                recommendation = generate_recommendation(skill, 0, required)
            priority = "High"
        elif current == 0:
            recommendation = generate_recommendation(skill, 0, required)
            priority = "High"
        else:
            recommendation = generate_recommendation(skill, current, required)
            priority = get_priority(current, required)

        if task:
            task.current_level = current
            task.required_level = required
            task.recommendation = recommendation
            task.priority = priority

        else:
            task = RoadmapTask(
                user_id=user.id,
                role=role,
                skill_name=skill,
                current_level=current,
                required_level=required,
                recommendation=recommendation,
                priority=priority
            )
            db.add(task)

    db.commit()

    return db.query(RoadmapTask).filter(
        RoadmapTask.user_id == user.id,
        RoadmapTask.role == role
    ).order_by(RoadmapTask.priority, RoadmapTask.skill_name).all()


# View a role-specific roadmap
@router.get("/{role}", response_model=list[RoadmapTaskResponse])
def get_roadmap(
    role: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    role = role.lower().replace("-", " ").replace("_", " ").strip()

    if role not in ROLE_REQUIREMENTS:
        raise HTTPException(status_code=404, detail="Role not supported")

    return db.query(RoadmapTask).filter(
        RoadmapTask.user_id == user.id,
        RoadmapTask.role == role
    ).all()


# Mark a roadmap task as completed
@router.put("/tasks/{task_id}/complete", response_model=RoadmapTaskCompleteResponse)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    task = db.query(RoadmapTask).filter(
        RoadmapTask.id == task_id,
        RoadmapTask.user_id == user.id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_completed = True

    db.commit()
    db.refresh(task)

    return {
        "message": "Roadmap task completed successfully",
        "task": task
    }
