from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, UniqueConstraint
)

from app.db.database import Base


class RoadmapTask(Base):
    __tablename__ = "roadmap_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    role = Column(String(100), nullable=False)
    skill_name = Column(String(100), nullable=False)

    current_level = Column(Integer, nullable=False)
    required_level = Column(Integer, nullable=False)

    recommendation = Column(String(500), nullable=False)
    priority = Column(String(20), nullable=False)

    is_completed = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "role", "skill_name",
            name="unique_user_roadmap_skill"
        ),
    )