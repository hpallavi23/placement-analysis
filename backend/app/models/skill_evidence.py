from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class SkillEvidence(Base):
    __tablename__ = "skill_evidence"

    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(
        Integer,
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    evidence_type = Column(String(50), nullable=False)
    title = Column(String(150), nullable=False)
    url = Column(String(500), nullable=False)
    description = Column(String(500), nullable=True)

    status = Column(String(20), nullable=False, default="pending")
    reviewer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reviewer_notes = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships configured with unambiguous foreign_keys
    skill = relationship("Skill", backref="evidence_submissions")
    user = relationship(
        "User",
        foreign_keys=[user_id],
        backref="submitted_evidence"
    )
    reviewer = relationship(
        "User",
        foreign_keys=[reviewer_id],
        backref="reviewed_evidence"
    )
