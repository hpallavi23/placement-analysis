"""Pydantic schemas for the Machine Learning Placement Prediction Engine."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlacementPredictionRequest(BaseModel):
    """Request schema for student campus placement prediction.

    Fields populated automatically from student profile and assessment when omitted:
    - cgpa: defaults to StudentProfile.cgpa
    - aptitude_test_score: defaults to Assessment.aptitude_score
    - soft_skills_rating: defaults to converted Assessment.communication_score (1.0 - 5.0)

    Required validated dataset inputs:
    - internships, projects, workshops_certifications, extracurricular_activities,
      placement_training, ssc_marks, hsc_marks
    """

    cgpa: float | None = Field(
        default=None,
        ge=0.0,
        le=10.0,
        description="Candidate CGPA (0.0 to 10.0). Defaults to authenticated profile if omitted.",
    )
    aptitude_test_score: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Aptitude screening score (0.0 to 100.0). Defaults to latest assessment if omitted.",
    )
    soft_skills_rating: float | None = Field(
        default=None,
        ge=1.0,
        le=5.0,
        description="Soft skills evaluation rating (1.0 to 5.0). Defaults to converted assessment communication score if omitted.",
    )

    internships: int = Field(
        ge=0,
        le=2,
        description="Number of completed internships.",
    )
    projects: int = Field(
        ge=0,
        le=3,
        description="Number of completed technical or academic projects.",
    )
    workshops_certifications: int = Field(
        ge=0,
        le=3,
        description="Number of workshops attended and certifications earned.",
    )
    extracurricular_activities: str = Field(
        description="Participation in extracurricular activities ('Yes' or 'No', case-insensitive).",
    )
    placement_training: str = Field(
        description="Participation in campus placement training programs ('Yes' or 'No', case-insensitive).",
    )
    ssc_marks: float = Field(
        ge=0.0,
        le=100.0,
        description="Senior Secondary School (10th grade) marks / percentage.",
    )
    hsc_marks: float = Field(
        ge=0.0,
        le=100.0,
        description="Higher Secondary School (12th grade) marks / percentage.",
    )

    @field_validator("extracurricular_activities", "placement_training", mode="before")
    @classmethod
    def normalize_binary_categorical(cls, v: Any) -> str:
        """Normalize boolean or string inputs to 'Yes' / 'No'."""
        if isinstance(v, bool):
            return "Yes" if v else "No"
        val_str = str(v).strip().capitalize()
        if val_str in ("Yes", "No"):
            return val_str
        if val_str.lower() in ("y", "true", "1"):
            return "Yes"
        if val_str.lower() in ("n", "false", "0"):
            return "No"
        raise ValueError("Must be 'Yes' or 'No' (or boolean True/False).")


class PlacementPredictionResponse(BaseModel):
    """Response schema containing the placement probability prediction."""

    placement_probability: float = Field(
        description="Estimated probability of campus placement (0.0 to 1.0) produced by the trained model."
    )
    placement_probability_pct: float = Field(
        description="Estimated placement probability formatted as a percentage (0.0% to 100.0%)."
    )
    predicted_class: str = Field(
        description="Model-predicted placement outcome category: 'Placed' or 'NotPlaced'."
    )
    prediction_label: int = Field(
        description="Binary classification label: 1 for Placed, 0 for NotPlaced."
    )
    model_name: str = Field(
        description="Identifier of the trained classification pipeline and training dataset source."
    )
    input_features_used: dict[str, Any] = Field(
        description="The resolved 10 feature values supplied to the preprocessing pipeline."
    )
    disclaimer: str = Field(
        description="Mandatory statistical disclaimer regarding model-based estimation."
    )
    technical_readiness_note: str = Field(
        description="Explicit clarification that this model does not measure programming or DSA skills."
    )

    model_config = ConfigDict(from_attributes=True)
