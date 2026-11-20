# NXTSTEP — AI-Based Personalized Placement Readiness & Opportunity Analysis System

NXTSTEP is a student-centric career readiness and opportunity analysis platform designed to help students evaluate their placement readiness, identify skill gaps for target industry roles, follow actionable learning roadmaps, and receive verified feedback on proof-of-work evidence submissions.

The platform implements a full-stack client-server architecture featuring a modern responsive web frontend, a robust FastAPI backend service, an SQLite relational database with SQLAlchemy ORM, JWT-based role authentication (Student and Reviewer), and an offline machine-learning training pipeline.

---

## Table of Contents

- [Key Implemented Features](#key-implemented-features)
- [System Architecture & Tech Stack](#system-architecture--tech-stack)
- [Machine Learning Training Pipeline](#machine-learning-training-pipeline)
- [User Workflows](#user-workflows)
  - [Student Workflow](#student-workflow)
  - [Reviewer Workflow](#reviewer-workflow)
- [Project Directory Structure](#project-directory-structure)
- [Setup & Running Instructions](#setup--running-instructions)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Environment Configuration](#2-environment-configuration)
  - [3. Backend Installation & Startup](#3-backend-installation--startup)
  - [4. Frontend Execution](#4-frontend-execution)
- [Running Automated Tests](#running-automated-tests)
- [Current Scope, Limitations & Future Roadmap](#current-scope-limitations--future-roadmap)
- [Academic Context](#academic-context)

---

## Key Implemented Features

### 1. Role-Based Authentication & Session Security
- **Secure Authentication**: User registration and login utilizing cryptographically hashed passwords (Bcrypt via Passlib) and standard JSON Web Tokens (JWT via python-jose).
- **Dual-Role Navigation**: Distinguishes between **Students** and authorized **Reviewers** (configured via environment allowlist).
  - Students access Dashboard, Skill Analysis, Learning Roadmap, and Opportunities.
  - Reviewers access a dedicated, role-guarded Evidence Review workspace.

### 2. Comprehensive Student Profiles
- Captures academic and placement background: Full Name, College, Branch, Graduation Year, CGPA, Target Job Role (e.g., Frontend Developer, Backend Developer, Full Stack Developer, Data Analyst), Project Count, Project Quality, and Project Summaries.
- Synchronized between local browser storage and backend database records.

### 3. Skill Assessment & Proficiency Calibration
- Multi-dimensional skill evaluation across four core domains:
  - **Technical Skills**: Programming (Python, JavaScript, Java), Web Development (HTML, CSS, React, Node.js), Databases (SQL, DBMS).
  - **Problem Solving**: Data Structures, Algorithms, Quantitative Aptitude, Logical Reasoning.
  - **Communication**: Verbal Communication, Written Communication, Presentation.
  - **Domain Knowledge**: System Design, Operating Systems, Computer Networks.
- Dynamic proficiency inputs (levels 1 to 5) with real-time radar and category distribution visualization.

### 4. Proof-of-Work Evidence Submission & Verification
- **Evidence Submission**: Students can submit tangible proof of competency (GitHub repositories, live deployments, certification links, project writeups) attached to individual skills.
- **Reviewer Workflow**: Reviewers view pending evidence submissions across all students with full submission context, and can **Approve** or **Reject** submissions with constructive reviewer feedback.
- **Evidence-Aware Proficiency Scoring**: When evidence is approved by a reviewer, the system mathematically calibrates the student's effective proficiency rating above their baseline self-rating, creating an auditable, verified skill profile.

### 5. Skill-Gap Analysis & Personalized Roadmap
- **Role Benchmarking**: Compares student proficiency profiles against target role requirements to highlight critical skill gaps, secondary gaps, and existing strengths.
- **Structured 4-Week Roadmap**: Generates a week-by-week actionable improvement plan with milestone tasks, priority levels, estimated durations, and toggleable completion tracking.

### 6. Placement Readiness Dashboard & Opportunity Matching
- **Composite Readiness Index**: Deterministic composite scoring across Academic Profile, Technical Proficiency, Problem Solving, Projects, and Soft Skills.
- **Opportunity Fit Analysis**: Matches student profiles against sample company placement requirements, calculating percentage match scores, identifying satisfied and missing criteria, and generating explainable fit summaries.

---

## System Architecture & Tech Stack

NXTSTEP follows a decoupled full-stack architecture:

```
[ Client: Web Browser ]
      │  ▲
      │  │  HTTP / REST JSON (CORS Enabled)
      │  │  JWT Bearer Authentication
      ▼  │
[ Server: FastAPI Application (Port 8000) ]
      │
      ├── Authentication & Security (OAuth2 / JWT / Passlib / Bcrypt)
      ├── API v1 Routers (Auth, Profile, Skills, Assessment, Roadmap, Opportunities)
      ├── Business Services (Evidence Scoring, Skill Gap, Readiness, Opportunity Fit)
      │
      ▼
[ Database: SQLite (SQLAlchemy 2.0 ORM) ]
```

### Technology Stack Details

- **Frontend**:
  - HTML5 & Responsive Semantic CSS3 (custom responsive styling, CSS Grid, Flexbox, accessible themes).
  - Modern Vanilla JavaScript (ES6+, `fetch` API, async/await, DOM manipulation).
  - Zero frontend build step required; runs directly in modern browsers.
- **Backend**:
  - **Framework**: Python 3.10+ with [FastAPI](https://fastapi.tiangolo.com/) (high-performance asynchronous ASGI web framework).
  - **Data Validation & Settings**: [Pydantic v2](https://docs.pydantic.dev/) and `pydantic-settings`.
  - **ORM & Database**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with [SQLite](https://www.sqlite.org/).
  - **Security & Crypto**: `python-jose` for JWT encoding/decoding; `passlib[bcrypt]` for secure password hashing.
  - **Server Engine**: [Uvicorn](https://www.uvicorn.org/) ASGI server.
- **Data Science & ML Pipeline (Offline)**:
  - `scikit-learn` (preprocessing pipelines, model training, evaluation metrics).
  - `pandas` and `numpy` (dataset exploration, feature engineering).
  - `joblib` (trained model artifact serialization).

---

## Machine Learning Training Pipeline

The repository includes an offline machine-learning training pipeline located in `backend/ml/`:

- **Dataset**: `backend/ml/data/Campus_Recruitment.csv` — Contains historical student academic metrics (secondary school percentage, higher secondary percentage, degree specialization, degree percentage, work experience, employability test scores, MBA scores, and placement outcomes).
- **Training Script**: `backend/ml/train.py` — Implements:
  - Stratified 80/20 train/test split.
  - Column transformation pipelines (`StandardScaler` for numeric features; `OneHotEncoder` for categorical features).
  - 5-Fold Stratified Cross-Validation comparing `LogisticRegression` and `RandomForestClassifier`.
  - Automated selection and serialization of the best-performing pipeline.
- **Saved Artifact**: `backend/ml/artifacts/placement_model.joblib` — The serialized trained model pipeline ready for offline analysis or future model serving.

> [!IMPORTANT]
> **Scoring Transparency & Explainability Notice:**
> In the current live prototype, real-time readiness scoring, skill-gap analysis, and roadmap recommendations are generated using **deterministic, explainable rule-based calculations**. The trained machine-learning model (`placement_model.joblib`) exists as an offline research artifact and is **not integrated into the live scoring loop**. This ensures that student evaluations remain transparent, reproducible, and directly auditable based on student-entered parameters and reviewer-verified evidence.

---

## User Workflows

### Student Workflow
1. **Sign Up / Sign In**: Register a new account or sign in with student credentials.
2. **Profile Configuration**: Fill in degree, branch, CGPA, target career role, and project background.
3. **Skill Evaluation**: Rate proficiencies from Level 1 to Level 5 across Technical, Problem Solving, Communication, and Domain Knowledge categories.
4. **Submit Proof-of-Work Evidence**: Under Skill Analysis, click **Submit Evidence** for any skill, providing a live repository/certificate URL and a detailed description of the project or coursework.
5. **Receive Calibrated Scoring**: Once a reviewer approves evidence, the skill reflects the approved submission and recalculates the evidence-calibrated readiness score.
6. **Follow Roadmap & Explore Opportunities**: Check the 4-week roadmap for targeted improvement steps and browse company opportunity cards to review eligibility and missing criteria.

### Reviewer Workflow
1. **Reviewer Login**: Log in using an authorized reviewer email account (configured in `backend/.env`).
2. **Automated Role Guarding**: The frontend navigation automatically isolates reviewer access, displaying only the **Evidence Review** portal and hiding student-only views.
3. **Pending Submissions Queue**: Reviewers view all unreviewed evidence submitted across all students, including student email, skill name, submission description, evidence URL, and timestamp.
4. **Approve or Reject**:
   - **Approve**: Confirms the validity of the work, granting proficiency boosts to the student's profile.
   - **Reject**: Marks the submission as rejected and allows the reviewer to provide constructive feedback explaining what was missing or required.
5. **Session Safety**: Logging out safely resets navigation back to standard defaults.

---

## Project Directory Structure

```
placement-analysis/
├── .gitignore                          # Excludes .venv, *.db, .env, caches, and backups
├── README.md                           # Project documentation (this file)
├── index.html                          # Complete frontend Single Page Application (SPA)
├── frontend/
│   └── js/
│       └── api.js                      # Client API module handling authentication and REST calls
└── backend/
    ├── .env.example                    # Sanitized environment template with dummy placeholder values
    ├── requirements.txt                # Production and development Python dependencies
    ├── app/
    │   ├── main.py                     # FastAPI entry point, CORS middleware, API router mounting
    │   ├── core/
    │   │   ├── config.py               # Application settings, JWT configuration, reviewer allowlist
    │   │   └── security.py             # Password hashing (bcrypt) and JWT token generation/validation
    │   ├── db/
    │   │   ├── database.py             # SQLAlchemy Base declarative class
    │   │   └── session.py              # SQLite engine and session dependency injection
    │   ├── models/                     # SQLAlchemy relational database entities
    │   │   ├── user.py                 # Users and credentials
    │   │   ├── student_profile.py      # Academic and profile parameters
    │   │   ├── skill.py                # Skills catalog and student skill proficiencies
    │   │   ├── skill_evidence.py       # Submitted evidence, status, and reviewer feedback
    │   │   ├── assessment.py           # Historical placement readiness assessments
    │   │   └── roadmap.py              # 4-week generated roadmap tasks and completion flags
    │   ├── schemas/                    # Pydantic request and response schemas (DTOs)
    │   │   ├── auth.py, student_profile.py, skill.py, skill_evidence.py,
    │   │   ├── assessment.py, roadmap.py, dashboard.py, opportunity.py,
    │   │   └── prediction.py, simulation.py
    │   ├── api/v1/endpoints/           # REST API endpoints
    │   │   ├── auth.py                 # /auth/register, /auth/login, /auth/me
    │   │   ├── profile.py              # /profile/me
    │   │   ├── skills.py               # /skills, evidence submission, reviewer verification
    │   │   ├── assessment.py           # /assessment/calculate, /assessment/latest, /assessment/history
    │   │   ├── roadmap.py              # /roadmap/generate, task completion toggles
    │   │   ├── dashboard.py            # /dashboard/summary
    │   │   ├── opportunities.py        # /opportunities/matched, /opportunities/all
    │   │   ├── prediction.py           # /prediction/predict (offline model invocation)
    │   │   └── simulation.py           # /simulation/simulate
    │   └── services/                   # Business logic and computational services
    │       ├── evidence_scoring.py     # Deterministic evidence calibration and boosts
    │       ├── readiness.py            # Multi-component readiness calculation
    │       ├── skill_gap.py            # Role benchmark comparison
    │       ├── roadmap.py              # Dynamic roadmap milestone generation
    │       ├── opportunity.py          # Opportunity matching and eligibility rules
    │       ├── dashboard.py            # Aggregated analytics summaries
    │       └── prediction.py, simulation.py
    ├── ml/
    │   ├── train.py                    # Scikit-learn training script (Stratified CV)
    │   ├── artifacts/
    │   │   └── placement_model.joblib  # Serialized trained model pipeline
    │   └── data/
    │       └── Campus_Recruitment.csv  # Historical placement training dataset
    └── tests/                          # Pytest automated test suite
        ├── conftest.py                 # In-memory test database, test client fixtures
        ├── test_auth_profile.py        # User registration, login, JWT validation, profile CRUD
        ├── test_assessments_skills_roadmap.py # Skills, assessments, and roadmap generation
        ├── test_evidence_scoring.py    # Submission, approval/rejection, reviewer allowlist, scoring
        └── test_analytics.py           # Dashboard summary, opportunities, simulation endpoints
```

---

## Setup & Running Instructions

### 1. Prerequisites
- **Python**: Version 3.10 or higher installed.
- **Node.js** *(Optional)*: Useful for running static syntax validation tools, but not required to run the application.
- **VS Code**: Recommended, with the [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) extension.
- **Web Browser**: Any modern browser (Google Chrome, Mozilla Firefox, Microsoft Edge).

---

### 2. Environment Configuration

1. Navigate to the `backend/` directory.
2. Copy `.env.example` and create a new file named `.env` in the same directory.
3. Open `backend/.env` and configure the required environment variables using your own secure values.
4. Generate a strong, random secret key for JWT authentication before running the application.

The `.env.example` file provides the configuration template required to get started.

**Security:** Never commit or share your actual `backend/.env` file. It contains local configuration and potentially sensitive values. The repository's `.gitignore` excludes `.env` files from Git tracking.

---

### 3. Backend Installation & Startup

1. Open a terminal and navigate to the project directory:
   ```bash
   cd placement-analysis
   ```

2. *(Recommended)* Create and activate a Python virtual environment:
   - **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install required Python packages:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. Launch the FastAPI backend server using the verified startup command:
   ```bash
   python -m uvicorn app.main:app --reload --app-dir backend
   ```
   The backend API will start on:
   ```
   http://127.0.0.1:8000
   ```
   Interactive Swagger documentation is available at `http://127.0.0.1:8000/docs`.

---

### 4. Frontend Execution

The frontend is served separately to simulate a real-world client-server environment:

1. Open the project root folder in **Visual Studio Code**.
2. Right-click on `index.html` in the file explorer and select **Open with Live Server**.
3. Your browser will open the application at:
   ```
   http://127.0.0.1:5500/index.html
   ```
4. The client will automatically connect to the backend running at `http://127.0.0.1:8000/api/v1`.

---

## Running Automated Tests

The backend includes a comprehensive automated test suite written with `pytest` and `httpx`. Tests execute against an isolated in-memory SQLite database, ensuring local development data is never altered.

To run the full test suite:

```bash
pytest backend/tests/
```

To run a specific test module with verbose output:

```bash
pytest backend/tests/test_evidence_scoring.py -v
```

### Test Suite Coverage
- `test_auth_profile.py`: Registration, authentication tokens, duplicate accounts, and student profile persistence.
- `test_assessments_skills_roadmap.py`: Skill batch updates, readiness index calculations, and 4-week roadmap generation.
- `test_evidence_scoring.py`: End-to-end evidence submission, reviewer authorization guards, approval/rejection workflows, and calibrated proficiency boosts.
- `test_analytics.py`: Dashboard summary aggregations, opportunity filtering, and placement chance simulation logic.

---

## Current Scope, Limitations & Future Roadmap

### Current Scope & Design Decisions
- **Deterministic Live Scoring**: The deployed application evaluates student readiness and opportunity fit through explainable, deterministic algorithms. This design was chosen intentionally to provide transparent, explainable recommendations that students and reviewers can audit without black-box opacity.
- **Local Relational Storage**: Utilizes SQLite for lightweight, self-contained development and demonstration.
- **Benchmark Data**: Role requirements and company opportunities are benchmarked against standardized industry job profiles rather than live third-party job board APIs.

### Future Scope
1. **Live ML Model Serving**: Deploy the scikit-learn placement prediction pipeline behind an asynchronous inference endpoint to present predictive benchmark distributions alongside deterministic readiness scores.
2. **Automated Evidence Ingestion**: Integrate third-party APIs (e.g., GitHub REST API for commit/repo activity, LeetCode/HackerRank profile scrapers, Credly certificate badges) to partially automate proof verification.
3. **Enterprise Database Support**: Transition database connections from SQLite to cloud-hosted PostgreSQL or MySQL with Alembic database migrations.
4. **Live Job Board Feeds**: Integrate real-time job posting APIs (e.g., Adzuna, LinkedIn Talent) for live opportunity matching.

---

## Academic Context

**Academic Project Title:** AI-Based Personalized Placement Readiness & Opportunity Analysis System  
**Developed as:** BTech Major Project  
**Repository:** [https://github.com/hpallavi23/placement-analysis](https://github.com/hpallavi23/placement-analysis)
