from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.simulation import WhatIfRequest, WhatIfResponse
from app.api.v1.endpoints.auth import get_current_user
from app.services.simulation import run_what_if_simulation


router = APIRouter(prefix="/simulation", tags=["What-If Simulation"])


@router.post("/what-if", response_model=WhatIfResponse)
def simulate_what_if(
    request: WhatIfRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return run_what_if_simulation(user.id, request, db)
