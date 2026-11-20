from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.api.v1.endpoints.auth import get_current_user
from app.services.dashboard import get_dashboard_summary


router = APIRouter(prefix="/dashboard", tags=["Student Dashboard"])


@router.get("/summary", response_model=DashboardResponse)
def get_student_dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return get_dashboard_summary(user, db)
