from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from app.db.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_name = Column(String(100), nullable=False)
    proficiency = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "skill_name", name="unique_user_skill"),
    )