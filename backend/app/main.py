from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.profile import router as profile_router
from app.models.assessment import Assessment
from app.api.v1.endpoints.assessment import router as assessment_router
from app.models.skill import Skill
from app.models.skill_evidence import SkillEvidence
from app.api.v1.endpoints.skills import router as skills_router
from app.models.roadmap import RoadmapTask
from app.api.v1.endpoints.roadmap import router as roadmap_router
from app.api.v1.endpoints.dashboard import router as dashboard_router
from app.api.v1.endpoints.opportunities import router as opportunities_router
from app.api.v1.endpoints.simulation import router as simulation_router
from app.api.v1.endpoints.prediction import router as prediction_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="NXTSTEP API",
    description="AI-Based Personalized Placement Readiness & Opportunity Analysis System",
    version="1.0.0",
    lifespan=lifespan
)

# Explicit development origins for React (3000), Vite (5173), and Live Server (5500)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")
app.include_router(assessment_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(roadmap_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(simulation_router, prefix="/api/v1")
app.include_router(prediction_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "message": "Welcome to NXTSTEP API"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "NXTSTEP backend is running"
    }
