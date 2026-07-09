from contextlib import asynccontextmanager
from datetime import datetime, timezone

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
from recommendation_service import current_recommendations, generate_recommendations, learning_plan
from schemas import (
    AssessmentAnswersRequest,
    AssessmentAttemptResponse,
    AssessmentResultResponse,
    AssessmentSaveResponse,
    AssessmentStatusResponse,
    CourseResponse,
    LearnerProgressResponse,
    LessonProgressUpdate,
    LessonResponse,
    LoginRequest,
    PersonalizedLearningPlanResponse,
    RecommendedLessonResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from seed_assessment import seed_initial_assessment
from seed_learning_content import seed_learning_content


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_assessment(db)
        seed_learning_content(db)
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


@app.get("/courses", response_model=list[CourseResponse])
def list_courses(
    language: str | None = None,
    proficiency_level: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Course).filter(models.Course.is_active == True)
    if language:
        query = query.filter(models.Course.language == language)
    if proficiency_level:
        query = query.filter(models.Course.proficiency_level == proficiency_level)
    return query.order_by(models.Course.language, models.Course.proficiency_level, models.Course.title).all()


@app.get("/lessons", response_model=list[LessonResponse])
def list_lessons(
    course: int | None = None,
    skill_type: str | None = None,
    proficiency_level: str | None = None,
    language: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Lesson).filter(models.Lesson.is_active == True)
    if course is not None:
        query = query.filter(models.Lesson.course_id == course)
    if skill_type:
        query = query.filter(models.Lesson.skill_type == skill_type)
    if proficiency_level:
        query = query.filter(models.Lesson.proficiency_level == proficiency_level)
    if language:
        query = query.filter(models.Lesson.language == language)
    return query.order_by(models.Lesson.proficiency_level, models.Lesson.difficulty_order).all()


@app.get("/recommendations/me", response_model=list[RecommendedLessonResponse])
def recommendations_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recommendations = current_recommendations(db, current_user)
    if recommendations:
        return recommendations
    return generate_recommendations(db, current_user)


@app.post("/recommendations/generate", response_model=list[RecommendedLessonResponse])
def recommendations_generate(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return generate_recommendations(db, current_user)


@app.patch("/lessons/{lesson_id}/progress", response_model=LearnerProgressResponse)
def update_lesson_progress(
    lesson_id: int,
    request: LessonProgressUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = (
        db.query(models.Lesson)
        .filter(models.Lesson.id == lesson_id, models.Lesson.is_active == True)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if request.status is None and request.progress_percentage is None:
        raise HTTPException(status_code=422, detail="Progress update is empty")

    progress = (
        db.query(models.LearnerProgress)
        .filter(
            models.LearnerProgress.user_id == current_user.id,
            models.LearnerProgress.lesson_id == lesson_id,
        )
        .first()
    )
    if not progress:
        progress = models.LearnerProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            status="not_started",
            progress_percentage=0,
        )
        db.add(progress)

    now = datetime.now(timezone.utc)
    if request.status is not None:
        progress.status = request.status
    if request.progress_percentage is not None:
        progress.progress_percentage = request.progress_percentage

    if progress.status == "completed":
        progress.progress_percentage = 100
        progress.completed_at = progress.completed_at or now
        progress.started_at = progress.started_at or now
    elif progress.status == "in_progress":
        progress.started_at = progress.started_at or now
        progress.completed_at = None
        if progress.progress_percentage <= 0:
            progress.progress_percentage = 1
    elif progress.status == "not_started":
        progress.progress_percentage = 0
        progress.started_at = None
        progress.completed_at = None

    if progress.progress_percentage == 100:
        progress.status = "completed"
        progress.completed_at = progress.completed_at or now
        progress.started_at = progress.started_at or now

    progress.last_accessed_at = now
    db.commit()
    db.refresh(progress)
    return progress


@app.get("/learning-plan/me", response_model=PersonalizedLearningPlanResponse)
def learning_plan_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return learning_plan(db, current_user)
