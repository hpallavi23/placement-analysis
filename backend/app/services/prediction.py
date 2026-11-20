"""Placement Prediction Engine Service.

Loads the Scikit-Learn pipeline trained on Krooz/Campus_Recruitment_CSV and
produces empirical placement probability estimates for authenticated students.

IMPORTANT:
- This is a dataset-based statistical estimate, not a guarantee of campus recruitment.
- This model evaluates macro-academic and extracurricular attributes; it does NOT evaluate
  programming languages, Data Structures & Algorithms (DSA), or technical interview readiness.
- For technical competency assessment, refer to Skill Gap and Opportunity Analysis.
"""

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.student_profile import StudentProfile
from app.schemas.prediction import PlacementPredictionRequest

# Robust path resolution relative to backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
MODEL_ARTIFACT_PATH = BASE_DIR / "ml" / "artifacts" / "placement_model.joblib"

MODEL_IDENTIFIER = (
    "LogisticRegression (Scikit-Learn Pipeline trained on Krooz/Campus_Recruitment_CSV)"
)

DISCLAIMER_TEXT = (
    "This placement prediction is an empirical statistical estimate derived from "
    "historical patterns in the Krooz/Campus_Recruitment_CSV dataset. It is not a guarantee "
    "of actual campus placement, job offer, or hiring commitment, nor does it serve as a complete "
    "measure of technical interview readiness."
)

TECHNICAL_READINESS_NOTE = (
    "Notice: This machine learning model evaluates academic performance, project counts, "
    "and screening metrics. It DOES NOT evaluate programming proficiency, Data Structures & Algorithms (DSA), "
    "frameworks, code quality, or live technical problem solving. Technical competencies should be evaluated "
    "using NXTSTEP Skill Gap Analysis and Placement Opportunity Analysis."
)

# Ordered feature list expected by the trained Scikit-Learn ColumnTransformer
EXPECTED_FEATURE_ORDER = [
    "CGPA",
    "Internships",
    "Projects",
    "Workshops/Certifications",
    "AptitudeTestScore",
    "SoftSkillsRating",
    "SSC_Marks",
    "HSC_Marks",
    "ExtracurricularActivities",
    "PlacementTraining",
]

_cached_model = None


def get_placement_model() -> Any:
    """Retrieve the cached placement model pipeline, loading it from disk on first call."""
    global _cached_model
    if _cached_model is None:
        if not MODEL_ARTIFACT_PATH.exists():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Placement prediction model artifact is unavailable at {MODEL_ARTIFACT_PATH}. "
                    "Ensure Stage 1 training has been completed."
                ),
            )
        try:
            _cached_model = joblib.load(MODEL_ARTIFACT_PATH)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load placement model artifact: {exc}",
            ) from exc

    return _cached_model


def predict_student_placement(
    user_id: int,
    request: PlacementPredictionRequest,
    db: Session,
) -> dict[str, Any]:
    """Resolve student features from profile/assessment or request payload and run ML inference."""
    # 1. Fetch user's student profile
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )

    # 2. Fetch user's latest assessment
    latest_assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == user_id)
        .order_by(Assessment.created_at.desc())
        .first()
    )

    # 3. Resolve CGPA: request override -> stored profile -> error (no silent default)
    if request.cgpa is not None:
        resolved_cgpa = float(request.cgpa)
    elif profile is not None and profile.cgpa is not None:
        resolved_cgpa = float(profile.cgpa)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "CGPA is required for placement prediction. "
                "Please update your student profile with a valid CGPA or provide 'cgpa' in the request."
            ),
        )

    # 4. Resolve AptitudeTestScore: request override -> stored assessment -> error (no silent default)
    if request.aptitude_test_score is not None:
        resolved_aptitude = float(request.aptitude_test_score)
    elif latest_assessment is not None and latest_assessment.aptitude_score is not None:
        resolved_aptitude = float(latest_assessment.aptitude_score)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Aptitude test score is required for placement prediction. "
                "Please complete a placement assessment or provide 'aptitude_test_score' in the request."
            ),
        )

    # 5. Resolve SoftSkillsRating: request override -> converted communication score -> error (no silent default)
    if request.soft_skills_rating is not None:
        resolved_soft_skills = float(request.soft_skills_rating)
    elif latest_assessment is not None and latest_assessment.communication_score is not None:
        # Convert existing 0-100 communication score to the dataset's 1.0-5.0 SoftSkillsRating scale:
        # soft_skills = 1.0 + (comm / 100.0) * 4.0
        comm_val = max(0.0, min(100.0, float(latest_assessment.communication_score)))
        converted_rating = round(1.0 + (comm_val / 100.0) * 4.0, 2)
        resolved_soft_skills = max(1.0, min(5.0, converted_rating))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Soft skills rating is required for placement prediction. "
                "Please complete an assessment with a communication score or provide 'soft_skills_rating' (1.0 - 5.0) in the request."
            ),
        )

    # 6. Assemble the 10 input features in exact expected column order
    input_features: dict[str, Any] = {
        "CGPA": resolved_cgpa,
        "Internships": int(request.internships),
        "Projects": int(request.projects),
        "Workshops/Certifications": int(request.workshops_certifications),
        "AptitudeTestScore": resolved_aptitude,
        "SoftSkillsRating": resolved_soft_skills,
        "SSC_Marks": float(request.ssc_marks),
        "HSC_Marks": float(request.hsc_marks),
        "ExtracurricularActivities": str(request.extracurricular_activities),
        "PlacementTraining": str(request.placement_training),
    }

    # 7. Convert to DataFrame preserving expected column names
    input_df = pd.DataFrame([input_features], columns=EXPECTED_FEATURE_ORDER)

    # 8. Load model and run inference
    model = get_placement_model()

    try:
        probabilities = model.predict_proba(input_df)[0]
        prediction_label = int(model.predict(input_df)[0])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed on model input: {exc}",
        ) from exc

    # Class 1 corresponds to 'Placed' (positive class)
    prob_placed = float(probabilities[1])
    prob_placed_pct = round(prob_placed * 100.0, 2)
    predicted_class = "Placed" if prediction_label == 1 else "NotPlaced"

    return {
        "placement_probability": round(prob_placed, 4),
        "placement_probability_pct": prob_placed_pct,
        "predicted_class": predicted_class,
        "prediction_label": prediction_label,
        "model_name": MODEL_IDENTIFIER,
        "input_features_used": input_features,
        "disclaimer": DISCLAIMER_TEXT,
        "technical_readiness_note": TECHNICAL_READINESS_NOTE,
    }
