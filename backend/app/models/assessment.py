from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from app.db.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    aptitude_score = Column(Float, nullable=False)
    technical_score = Column(Float, nullable=False)
    communication_score = Column(Float, nullable=False)
    problem_solving_score = Column(Float, nullable=False)

    readiness_score = Column(Float, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )