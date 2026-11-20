from pydantic import BaseModel, ConfigDict, Field


class StudentProfileCreate(BaseModel):
    full_name: str
    college: str | None = None
    branch: str | None = None
    graduation_year: int | None = Field(default=None, ge=2020, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)


class StudentProfileUpdate(BaseModel):
    full_name: str | None = None
    college: str | None = None
    branch: str | None = None
    graduation_year: int | None = Field(default=None, ge=2020, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)


class StudentProfileResponse(StudentProfileCreate):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)