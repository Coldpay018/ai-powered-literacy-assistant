from contextlib import asynccontextmanager
import hashlib
import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

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
from learning_content_service import (
    get_published_course,
    get_published_lesson,
    get_published_module,
    list_published_courses,
    list_published_modules,
    serialize_course_detail,
    serialize_course_summary,
    serialize_lesson_detail,
    serialize_module_detail,
    serialize_module_summary,
    validate_difficulty_filter,
    validate_language_filter,
    validate_skill_filter,
)
import models
from recommendation_service import current_recommendations, generate_recommendations, learning_plan
from personalization_service import build_personalization_profile
from adaptive_difficulty_service import evaluate_difficulty
from question_difficulty_service import build_starting_difficulty_profile
from schema_updates import apply_sqlite_schema_updates
from schemas import (
    AssessmentAnswersRequest,
    AssessmentAttemptResponse,
    AssessmentResultResponse,
    AssessmentSaveResponse,
    AssessmentStatusResponse,
    CourseDetailResponse,
    CourseSummaryResponse,
    LearnerProgressResponse,
    LessonDetailResponse,
    LessonProgressUpdate,
    LessonPlayerResponse,
    LessonQuizSubmitRequest,
    LessonQuizSubmitResponse,
    LessonResponse,
    LoginRequest,
    ModuleDetailResponse,
    ModuleSummaryResponse,
    PersonalizedLearningPlanResponse,
    PersonalizationProfileResponse,
    RecommendedLessonResponse,
    StartingDifficultyResponse,
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
    apply_sqlite_schema_updates(engine)
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


def _validate_user_language_pair(
    comfortable_language: str | None,
    learning_language: str | None,
) -> None:
    if comfortable_language and learning_language and comfortable_language == learning_language:
        raise HTTPException(
            status_code=422,
            detail="Comfortable language and learning language must be different",
        )


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
        comfortable_language=user.comfortable_language,
        learning_language=user.learning_language,
        experience_level=user.experience_level,
        preferred_language=user.comfortable_language,
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
    next_comfortable_language = updates.get(
        "comfortable_language",
        current_user.comfortable_language,
    )
    next_learning_language = updates.get(
        "learning_language",
        current_user.learning_language,
    )
    _validate_user_language_pair(next_comfortable_language, next_learning_language)

    if "comfortable_language" in updates:
        updates["preferred_language"] = updates["comfortable_language"]

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


@app.get("/courses", response_model=list[CourseSummaryResponse])
def list_courses(
    skill: str | None = Query(default=None),
    difficulty_level: str | None = Query(default=None),
    language: str | None = Query(default=None),
    age: int | None = Query(default=None, ge=1),
    proficiency_level: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    validated_skill = validate_skill_filter(skill)
    validated_difficulty = validate_difficulty_filter(difficulty_level)
    validated_language = validate_language_filter(language)
    validated_proficiency = validate_difficulty_filter(proficiency_level)
    courses = list_published_courses(
        db,
        skill=validated_skill,
        difficulty_level=validated_difficulty,
        language=validated_language,
        age=age,
        proficiency_level=validated_proficiency,
    )
    return [serialize_course_summary(course) for course in courses]


@app.get("/courses/{course_id}", response_model=CourseDetailResponse)
def read_course(course_id: int, db: Session = Depends(get_db)):
    return serialize_course_detail(get_published_course(db, course_id))


@app.get("/courses/{course_id}/modules", response_model=list[ModuleSummaryResponse])
def list_course_modules(course_id: int, db: Session = Depends(get_db)):
    modules = list_published_modules(db, course_id)
    return [serialize_module_summary(module) for module in modules]


@app.get("/modules/{module_id}", response_model=ModuleDetailResponse)
def read_module(module_id: int, db: Session = Depends(get_db)):
    return serialize_module_detail(get_published_module(db, module_id))


@app.get("/lessons", response_model=list[LessonResponse])
def list_lessons(
    course: int | None = None,
    skill_type: str | None = None,
    proficiency_level: str | None = None,
    language: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Lesson).filter(
        models.Lesson.is_active == True,
        models.Lesson.is_published == True,
    )
    if course is not None:
        query = query.filter(models.Lesson.course_id == course)
    if skill_type:
        query = query.filter(models.Lesson.skill_type == skill_type)
    if proficiency_level:
        query = query.filter(models.Lesson.proficiency_level == proficiency_level)
    if language:
        query = query.filter(models.Lesson.language == language)
    lessons = query.options(joinedload(models.Lesson.module)).all()
    return sorted(
        lessons,
        key=lambda lesson: (
            lesson.module.sequence_order if lesson.module and lesson.module.sequence_order is not None else 10**9,
            lesson.module.title if lesson.module else "",
            lesson.sequence_order if lesson.sequence_order is not None else 0,
            lesson.title or "",
        ),
    )


@app.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
def read_lesson(lesson_id: int, db: Session = Depends(get_db)):
    return serialize_lesson_detail(get_published_lesson(db, lesson_id))


def _get_or_create_lesson_progress(
    db: Session,
    user_id: int,
    lesson_id: int,
) -> models.LearnerProgress:
    lesson = (
        db.query(models.Lesson)
        .filter(models.Lesson.id == lesson_id, models.Lesson.is_active == True)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    progress = (
        db.query(models.LearnerProgress)
        .filter(
            models.LearnerProgress.user_id == user_id,
            models.LearnerProgress.lesson_id == lesson_id,
        )
        .first()
    )
    if not progress:
        progress = models.LearnerProgress(
            user_id=user_id,
            course_id=lesson.course_id,
            module_id=lesson.module_id,
            lesson_id=lesson_id,
            completion_status="not_started",
            status="not_started",
            progress_percentage=0,
            current_difficulty=lesson.proficiency_level,
        )
        db.add(progress)
        db.flush()
    progress.course_id = lesson.course_id
    progress.module_id = lesson.module_id
    progress.current_difficulty = lesson.proficiency_level
    if not progress.completion_status:
        progress.completion_status = progress.status
    return progress


def _course_lessons(course: models.Course) -> list[models.Lesson]:
    ordered_lessons: list[models.Lesson] = []

    modules = sorted(
        [module for module in course.modules if module.is_published],
        key=lambda module: (
            module.sequence_order if module.sequence_order is not None else 0,
            module.title or "",
        ),
    )
    for module in modules:
        module_lessons = sorted(
            [lesson for lesson in module.lessons if lesson.is_active and lesson.is_published],
            key=lambda lesson: (
                lesson.sequence_order if lesson.sequence_order is not None else 0,
                lesson.title or "",
            ),
        )
        ordered_lessons.extend(module_lessons)

    standalone_lessons = sorted(
        [
            lesson
            for lesson in course.lessons
            if lesson.is_active and lesson.is_published and lesson.module_id is None
        ],
        key=lambda lesson: (
            lesson.sequence_order if lesson.sequence_order is not None else 0,
            lesson.title or "",
        ),
    )
    ordered_lessons.extend(standalone_lessons)
    return ordered_lessons


def _progress_status_map(
    db: Session,
    user_id: int,
    lessons: list[models.Lesson],
) -> dict[int, models.LearnerProgress]:
    lesson_ids = [lesson.id for lesson in lessons]
    if not lesson_ids:
        return {}
    rows = (
        db.query(models.LearnerProgress)
        .filter(
            models.LearnerProgress.user_id == user_id,
            models.LearnerProgress.lesson_id.in_(lesson_ids),
        )
        .all()
    )
    return {row.lesson_id: row for row in rows}


def _sync_progress_metadata(progress: models.LearnerProgress, lesson: models.Lesson) -> None:
    progress.course_id = lesson.course_id
    progress.module_id = lesson.module_id
    progress.current_difficulty = lesson.proficiency_level
    progress.completion_status = progress.status


def _is_lesson_unlocked(
    lesson: models.Lesson,
    lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> bool:
    index = next((position for position, item in enumerate(lessons) if item.id == lesson.id), 0)
    if index <= 0:
        return True
    current_progress = progress_by_lesson.get(lesson.id)
    if current_progress and current_progress.status in {"in_progress", "completed"}:
        return True
    previous_lesson = lessons[index - 1]
    previous_progress = progress_by_lesson.get(previous_lesson.id)
    return previous_progress is not None and previous_progress.status == "completed"


def _navigation_item(
    lesson: models.Lesson | None,
    lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> dict | None:
    if lesson is None:
        return None
    progress = progress_by_lesson.get(lesson.id)
    is_unlocked = _is_lesson_unlocked(lesson, lessons, progress_by_lesson)
    return {
        "id": lesson.id,
        "title": lesson.title,
        "status": progress.status if progress else "not_started",
        "is_unlocked": is_unlocked,
        "locked": not is_unlocked,
    }


@app.get("/lessons/{lesson_id}/player", response_model=LessonPlayerResponse)
def read_lesson_player(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = get_published_lesson(db, lesson_id)
    lessons = _course_lessons(lesson.course)
    progress_by_lesson = _progress_status_map(db, current_user.id, lessons)
    is_unlocked = _is_lesson_unlocked(lesson, lessons, progress_by_lesson)
    index = next((position for position, item in enumerate(lessons) if item.id == lesson.id), 0)
    previous_lesson = lessons[index - 1] if index > 0 else None
    next_lesson = lessons[index + 1] if index + 1 < len(lessons) else None

    progress = progress_by_lesson.get(lesson.id)
    if is_unlocked:
        progress = _get_or_create_lesson_progress(db, current_user.id, lesson.id)
        _sync_progress_metadata(progress, lesson)
        now = datetime.now(timezone.utc)
        progress.last_accessed_at = now
        if progress.status == "not_started":
            progress.status = "in_progress"
            progress.completion_status = "in_progress"
            progress.started_at = progress.started_at or now
            progress.progress_percentage = max(progress.progress_percentage, 1)
        db.commit()
        db.refresh(progress)
        progress_by_lesson[lesson.id] = progress
    else:
        progress = _get_or_create_lesson_progress(db, current_user.id, lesson.id)
        _sync_progress_metadata(progress, lesson)
        progress.last_accessed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(progress)
        progress_by_lesson[lesson.id] = progress

    detail = serialize_lesson_detail(lesson)
    if not is_unlocked:
        detail["content_blocks"] = []
        detail["questions"] = []

    return {
        **detail,
        "progress": progress,
        "is_unlocked": is_unlocked,
        "locked": not is_unlocked,
        "lock_reason": "Complete the previous lesson to unlock this lesson." if not is_unlocked else None,
        "previous_lesson": _navigation_item(previous_lesson, lessons, progress_by_lesson),
        "next_lesson": _navigation_item(next_lesson, lessons, progress_by_lesson),
    }


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
    if (
        request.status is None
        and request.progress_percentage is None
        and request.last_content_block_id is None
        and request.time_spent_seconds is None
    ):
        raise HTTPException(status_code=422, detail="Progress update is empty")

    if request.last_content_block_id is not None:
        valid_block = (
            db.query(models.LessonContent)
            .filter(
                models.LessonContent.id == request.last_content_block_id,
                models.LessonContent.lesson_id == lesson_id,
            )
            .first()
        )
        if not valid_block:
            raise HTTPException(status_code=422, detail="Invalid content block for lesson")

    course = (
        db.query(models.Course)
        .options(
            joinedload(models.Course.modules).joinedload(models.CourseModule.lessons),
            joinedload(models.Course.lessons),
        )
        .filter(models.Course.id == lesson.course_id)
        .first()
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    lessons = _course_lessons(course)
    progress_by_lesson = _progress_status_map(db, current_user.id, lessons)
    if not _is_lesson_unlocked(lesson, lessons, progress_by_lesson):
        raise HTTPException(status_code=423, detail="Lesson is locked")

    progress = _get_or_create_lesson_progress(db, current_user.id, lesson_id)
    _sync_progress_metadata(progress, lesson)

    now = datetime.now(timezone.utc)
    if request.status is not None:
        progress.status = request.status
    if request.progress_percentage is not None:
        progress.progress_percentage = request.progress_percentage
    if request.last_content_block_id is not None:
        progress.last_content_block_id = request.last_content_block_id
    time_spent_increment = (
        request.time_spent_seconds
        if request.time_spent_seconds is not None
        else request.time_spent
    )
    if time_spent_increment is not None:
        progress.time_spent_seconds += time_spent_increment
        progress.time_spent += time_spent_increment

    if progress.status == "completed":
        progress.progress_percentage = 100
        progress.completion_status = "completed"
        progress.completed_at = progress.completed_at or now
        progress.started_at = progress.started_at or now
    elif progress.status == "in_progress":
        progress.completion_status = "in_progress"
        progress.started_at = progress.started_at or now
        progress.completed_at = None
        if progress.progress_percentage <= 0:
            progress.progress_percentage = 1
    elif progress.status == "not_started":
        progress.completion_status = "not_started"
        progress.progress_percentage = 0
        progress.started_at = None
        progress.completed_at = None

    if progress.progress_percentage == 100:
        progress.status = "completed"
        progress.completion_status = "completed"
        progress.completed_at = progress.completed_at or now
        progress.started_at = progress.started_at or now

    progress.last_accessed_at = now
    db.commit()
    db.refresh(progress)
    return progress


@app.post("/lessons/{lesson_id}/quiz/submit", response_model=LessonQuizSubmitResponse)
def submit_lesson_quiz(
    lesson_id: int,
    request: LessonQuizSubmitRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = get_published_lesson(db, lesson_id)
    lessons = _course_lessons(lesson.course)
    progress_by_lesson = _progress_status_map(db, current_user.id, lessons)
    if not _is_lesson_unlocked(lesson, lessons, progress_by_lesson):
        raise HTTPException(status_code=423, detail="Lesson is locked")

    questions = sorted(lesson.questions, key=lambda item: item.sequence_order)
    if not questions:
        raise HTTPException(status_code=422, detail="Lesson has no quiz questions")

    normalized_answers = json.dumps(
        {str(key): value for key, value in sorted(request.answers.items(), key=lambda item: str(item[0]))},
        ensure_ascii=False,
        sort_keys=True,
    )
    submission_hash = hashlib.sha256(
        f"{current_user.id}:{lesson_id}:{normalized_answers}:{request.time_spent_seconds}".encode("utf-8")
    ).hexdigest()
    duplicate_attempt = (
        db.query(models.LessonAttempt)
        .filter(
            models.LessonAttempt.user_id == current_user.id,
            models.LessonAttempt.lesson_id == lesson_id,
            models.LessonAttempt.submission_hash == submission_hash,
        )
        .first()
    )

    total_points = sum(question.points for question in questions)
    awarded_points = 0
    correct_count = 0
    results = []
    difficulty_adjustments = []

    for question in questions:
        submitted = (request.answers.get(question.id) or "").strip().lower()
        expected = (question.correct_answer or "").strip().lower()
        is_correct = bool(submitted) and submitted == expected
        points_awarded = question.points if is_correct else 0
        awarded_points += points_awarded
        correct_count += 1 if is_correct else 0
        results.append(
            {
                "question_id": question.id,
                "correct": is_correct,
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
                "points_awarded": points_awarded,
                "points": question.points,
            }
        )
        if not duplicate_attempt:
            difficulty_adjustments.append(
                evaluate_difficulty(
                    db,
                    current_user.id,
                    question.skill or question.skill_type,
                    is_correct,
                    context={
                        "source": "lesson_quiz",
                        "lesson_id": lesson_id,
                        "question_id": question.id,
                        "attempt_id": duplicate_attempt.id if duplicate_attempt else None,
                        "event_id": f"lesson_quiz:{submission_hash}:{question.id}",
                        "answer_hash": submission_hash,
                    },
                    commit=False,
                )
            )

    score = round((awarded_points / total_points) * 100, 2) if total_points else 0
    if duplicate_attempt:
        progress = _get_or_create_lesson_progress(db, current_user.id, lesson_id)
        _sync_progress_metadata(progress, lesson)
        return {
            "score": duplicate_attempt.score,
            "total_points": duplicate_attempt.total_points,
            "correct_answers": duplicate_attempt.correct_answers,
            "total_questions": duplicate_attempt.total_questions,
            "passed": duplicate_attempt.score >= 60,
            "progress": progress,
            "results": results,
            "difficulty_adjustments": [],
        }

    progress = _get_or_create_lesson_progress(db, current_user.id, lesson_id)
    _sync_progress_metadata(progress, lesson)
    now = datetime.now(timezone.utc)
    progress.status = "completed"
    progress.completion_status = "completed"
    progress.progress_percentage = 100
    progress.questions_attempted += len(questions)
    progress.correct_answers += correct_count
    progress.incorrect_answers += len(questions) - correct_count
    progress.score = score
    progress.best_quiz_score = max(progress.best_quiz_score or 0, score)
    progress.attempt_count += 1
    progress.time_spent_seconds += request.time_spent_seconds
    progress.time_spent += request.time_spent_seconds
    progress.started_at = progress.started_at or now
    progress.completed_at = progress.completed_at or now
    progress.last_accessed_at = now

    attempt = models.LessonAttempt(
        user_id=current_user.id,
        lesson_id=lesson_id,
        attempt_number=progress.attempt_count,
        score=score,
        total_points=total_points,
        correct_answers=correct_count,
        total_questions=len(questions),
        time_spent_seconds=request.time_spent_seconds,
        submission_hash=submission_hash,
        completed_at=now,
    )
    db.add(attempt)
    db.commit()
    db.refresh(progress)
    return {
        "score": score,
        "total_points": total_points,
        "correct_answers": correct_count,
        "total_questions": len(questions),
        "passed": score >= 60,
        "progress": progress,
        "results": results,
        "difficulty_adjustments": difficulty_adjustments,
    }


@app.get("/progress/me", response_model=list[LearnerProgressResponse])
def progress_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.LearnerProgress)
        .filter(models.LearnerProgress.user_id == current_user.id)
        .order_by(models.LearnerProgress.last_accessed_at.desc().nullslast(), models.LearnerProgress.id.desc())
        .all()
    )


@app.get("/learning-plan/me", response_model=PersonalizedLearningPlanResponse)
def learning_plan_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return learning_plan(db, current_user)


@app.get("/personalization/me", response_model=PersonalizationProfileResponse)
def personalization_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    progress_records = (
        db.query(models.LearnerProgress)
        .filter(models.LearnerProgress.user_id == current_user.id)
        .options(joinedload(models.LearnerProgress.lesson))
        .all()
    )
    return build_personalization_profile(current_user, progress_records)


@app.get("/difficulty/me", response_model=StartingDifficultyResponse)
def starting_difficulty_me(
    skill: str | None = Query(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_starting_difficulty_profile(db, current_user, skill=skill)
