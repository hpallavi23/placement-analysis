"""Placement Prediction Engine Endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.prediction import (
    PlacementPredictionRequest,
    PlacementPredictionResponse,
)
from app.services.prediction import predict_student_placement

router = APIRouter(prefix="/predictions", tags=["Placement Prediction Engine"])


@router.post(
    "/placement-probability",
    response_model=PlacementPredictionResponse,
    summary="Predict Student Campus Placement Probability",
)
def predict_placement_probability(
    request: PlacementPredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Predict campus recruitment placement probability using the trained machine learning pipeline.

    - Resolves CGPA, Aptitude score, and Soft Skills rating from the student's stored profile/assessment
      when omitted, or accepts explicit overrides in the request.
    - Requires additional validated dataset inputs: internships, projects, workshops_certifications,
      extracurricular_activities, placement_training, ssc_marks, and hsc_marks.
    - Evaluates the 10 features via the trained Scikit-Learn LogisticRegression pipeline.
    - Returns placement probability, predicted category ('Placed' / 'NotPlaced'), model provenance,
      and transparency disclaimers.
    """
    return predict_student_placement(current_user.id, request, db)
