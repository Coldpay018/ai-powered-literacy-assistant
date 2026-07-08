from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from assessment_service import (
    current_attempt,
    get_result,
    get_status,
    save_answers,
    start_or_resume,
    submit_attempt,
)
from auth import create_access_token, decode_access_token, hash_password, verify_password
from database import Base, SessionLocal, engine
import models
from schemas import (
    AssessmentAnswersRequest,
    AssessmentAttemptResponse,
    AssessmentResultResponse,
    AssessmentSaveResponse,
    AssessmentStatusResponse,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from seed_assessment import seed_initial_assessment


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_assessment(db)
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return user


@app.get("/")
def read_root():
    return {"message": "Literacy Learning Assistant backend is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = (
        db.query(models.User).filter(models.User.email == user.email).first()
    )

    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = models.User(
        full_name=user.full_name,
        age=user.age,
        email=user.email,
        hashed_password=hash_password(user.password),
        preferred_language=user.preferred_language,
        education_level=user.education_level,
        role=user.role,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.post("/login", response_model=TokenResponse)
def login_user(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.email == login_data.email)
        .first()
    )

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user_id=user.id)

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserResponse)
def read_current_user(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.patch("/users/me", response_model=UserResponse)
def update_current_user(
    user_update: UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = user_update.model_dump(exclude_unset=True)

    if "email" in updates and updates["email"] != current_user.email:
        existing_user = (
            db.query(models.User)
            .filter(models.User.email == updates["email"], models.User.id != current_user.id)
            .first()
        )

        if existing_user:
            raise HTTPException(status_code=400, detail="Email is already registered")

    for field, value in updates.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@app.get("/assessment/status", response_model=AssessmentStatusResponse)
def assessment_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_status(db, current_user)


@app.post("/assessment/start", response_model=AssessmentAttemptResponse)
def assessment_start(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return start_or_resume(db, current_user)


@app.get("/assessment/current", response_model=AssessmentAttemptResponse)
def assessment_current(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return current_attempt(db, current_user)


@app.put("/assessment/attempts/{attempt_id}/answers", response_model=AssessmentSaveResponse)
def assessment_save_answers(
    attempt_id: int,
    request: AssessmentAnswersRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return save_answers(db, current_user, attempt_id, request.answers)


@app.post("/assessment/attempts/{attempt_id}/submit", response_model=AssessmentResultResponse)
def assessment_submit(
    attempt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_attempt(db, current_user, attempt_id)


@app.get("/assessment/result", response_model=AssessmentResultResponse)
def assessment_result(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_result(db, current_user)
