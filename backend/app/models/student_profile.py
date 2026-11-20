from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    full_name = Column(String(150), nullable=False)
    college = Column(String(200))
    branch = Column(String(150))
    graduation_year = Column(Integer)
    cgpa = Column(Float)

    user = relationship("User", backref="student_profile")