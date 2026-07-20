from contextlib import asynccontextmanager
import hashlib
import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from assessment_flow_service import (
    complete_assessment,
    current_attempt,
    get_status,
    start_or_resume,
    submit_assessment_answer,
)
from assessment_service import get_result
from auth import create_access_token, decode_access_token, hash_password, verify_password
from database import Base, SessionLocal, engine
from gamification_service import (
    award_lesson_completion_xp,
    award_perfect_quiz_xp,
    get_user_badges,
    get_recent_xp_transactions,
    get_streak_summary,
    get_total_xp,
    get_week_start,
    get_xp_earned_since,
    seed_badges,
)
from flashcard_service import (
    get_due_flashcards,
    get_flashcard_deck,
    list_flashcard_decks,
    record_flashcard_review,
)
from puzzle_service import (
    get_puzzle_set,
    get_puzzle_set_progress,
    list_puzzle_sets,
    submit_puzzle_attempt,
)
from learning_content_service import (
    get_published_course,
    get_published_lesson,
    get_published_module,
    get_or_create_lesson_progress,
    is_lesson_unlocked,
    list_published_courses,
    list_published_modules,
    navigation_item,
    ordered_course_lessons,
    progress_status_map,
    repair_initial_unlock_state,
    serialize_course_detail,
    serialize_course_summary,
    serialize_lesson_detail,
    serialize_module_detail,
    serialize_module_summary,
    start_unlocked_lesson_progress,
    sync_progress_metadata,
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
    AssessmentAttemptResponse,
    AssessmentAnswerRequest,
    AssessmentAnswerResponse,
    AssessmentSpokenAnswerRequest,
    AssessmentResultResponse,
    AssessmentStatusResponse,
    BadgeSummaryResponse,
    CourseDetailResponse,
    CourseSummaryResponse,
    FlashcardDeckResponse,
    FlashcardResponse,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
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
    PuzzleAttemptRequest,
    PuzzleAttemptResponse,
    PuzzleSetProgressResponse,
    PuzzleSetResponse,
    RecommendedLessonResponse,
    StartingDifficultyResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    XPSummaryResponse,
)
from spoken_answer_service import submit_spoken_assessment_answer
from seed_assessment import seed_initial_assessment
from seed_learning_content import seed_learning_content


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    apply_sqlite_schema_updates(engine)
    db = SessionLocal()
    try:
        seed_badges(db)
        seed_initial_assessment(db)
        seed_learning_content(db)
        db.commit()
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


@app.put("/assessment/attempts/{attempt_id}/answers", response_model=AssessmentAnswerResponse)
@app.post("/assessment/attempts/{attempt_id}/answer", response_model=AssessmentAnswerResponse)
def assessment_answer(
    attempt_id: int,
    request: AssessmentAnswerRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_assessment_answer(db, current_user, attempt_id, request.attempt_question_id, request.answer)


@app.post("/assessment/attempts/{attempt_id}/spoken-answer", response_model=AssessmentAnswerResponse)
def assessment_spoken_answer(
    attempt_id: int,
    request: AssessmentSpokenAnswerRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_spoken_assessment_answer(
        db,
        current_user,
        attempt_id,
        request.attempt_question_id,
        request.spoken_text,
    )


@app.post("/assessment/attempts/{attempt_id}/submit", response_model=AssessmentResultResponse)
@app.post("/assessment/attempts/{attempt_id}/complete", response_model=AssessmentResultResponse)
def assessment_submit(
    attempt_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return complete_assessment(db, current_user, attempt_id)


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
def read_lesson(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = get_published_lesson(db, lesson_id)
    lessons = ordered_course_lessons(lesson.course)
    progress_by_lesson = progress_status_map(db, current_user.id, lessons)
    repair_initial_unlock_state(db, current_user.id, lessons, progress_by_lesson)
    if not is_lesson_unlocked(lesson, lessons, progress_by_lesson):
        raise HTTPException(status_code=423, detail="Lesson is locked")
    db.commit()
    return {
        **serialize_lesson_detail(lesson),
        "is_unlocked": True,
        "locked": False,
    }


@app.get("/lessons/{lesson_id}/player", response_model=LessonPlayerResponse)
def read_lesson_player(
    lesson_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = get_published_lesson(db, lesson_id)
    lessons = ordered_course_lessons(lesson.course)
    progress_by_lesson = progress_status_map(db, current_user.id, lessons)
    repair_initial_unlock_state(db, current_user.id, lessons, progress_by_lesson)
    is_unlocked = is_lesson_unlocked(lesson, lessons, progress_by_lesson)
    index = next((position for position, item in enumerate(lessons) if item.id == lesson.id), 0)
    previous_lesson = lessons[index - 1] if index > 0 else None
    next_lesson = lessons[index + 1] if index + 1 < len(lessons) else None

    if not is_unlocked:
        db.rollback()
        raise HTTPException(status_code=423, detail="Lesson is locked")

    progress = start_unlocked_lesson_progress(db, current_user.id, lesson)
    db.commit()
    db.refresh(progress)
    progress_by_lesson[lesson.id] = progress

    detail = serialize_lesson_detail(lesson)

    return {
        **detail,
        "progress": progress,
        "is_unlocked": is_unlocked,
        "locked": not is_unlocked,
        "lock_reason": None,
        "previous_lesson": navigation_item(previous_lesson, lessons, progress_by_lesson),
        "next_lesson": navigation_item(next_lesson, lessons, progress_by_lesson),
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
    lessons = ordered_course_lessons(course)
    progress_by_lesson = progress_status_map(db, current_user.id, lessons)
    repair_initial_unlock_state(db, current_user.id, lessons, progress_by_lesson)
    if not is_lesson_unlocked(lesson, lessons, progress_by_lesson):
        raise HTTPException(status_code=423, detail="Lesson is locked")

    progress = get_or_create_lesson_progress(db, current_user.id, lesson)

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
    if progress.completion_status == "completed":
        award_lesson_completion_xp(db, user_id=current_user.id, lesson_id=lesson_id)
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
    lessons = ordered_course_lessons(lesson.course)
    progress_by_lesson = progress_status_map(db, current_user.id, lessons)
    repair_initial_unlock_state(db, current_user.id, lessons, progress_by_lesson)
    if not is_lesson_unlocked(lesson, lessons, progress_by_lesson):
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
        progress = get_or_create_lesson_progress(db, current_user.id, lesson)
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

    progress = get_or_create_lesson_progress(db, current_user.id, lesson)
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
    award_lesson_completion_xp(db, user_id=current_user.id, lesson_id=lesson_id)
    award_perfect_quiz_xp(db, user_id=current_user.id, lesson_id=lesson_id, score=score)
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


@app.get("/gamification/xp", response_model=XPSummaryResponse)
def gamification_xp(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    week_start = get_week_start()
    return {
        "total_xp": get_total_xp(db, current_user.id),
        "xp_earned_this_week": get_xp_earned_since(db, current_user.id, week_start),
        "recent_transactions": get_recent_xp_transactions(db, current_user.id),
        **get_streak_summary(db, current_user.id),
    }


@app.get("/gamification/badges", response_model=BadgeSummaryResponse)
def gamification_badges(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = get_user_badges(db, current_user.id)
    db.commit()
    return response


@app.get("/flashcards/decks", response_model=list[FlashcardDeckResponse])
def flashcard_decks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_flashcard_decks(db, current_user.id)


@app.get("/flashcards/decks/{deck_id}", response_model=FlashcardDeckResponse)
def flashcard_deck(
    deck_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_flashcard_deck(db, current_user.id, deck_id)


@app.get("/flashcards/decks/{deck_id}/due", response_model=list[FlashcardResponse])
def flashcard_due_cards(
    deck_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_due_flashcards(db, user_id=current_user.id, deck_id=deck_id)


@app.post("/flashcards/{flashcard_id}/review", response_model=FlashcardReviewResponse)
def flashcard_review(
    flashcard_id: int,
    request: FlashcardReviewRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = record_flashcard_review(
        db,
        user_id=current_user.id,
        flashcard_id=flashcard_id,
        outcome=request.outcome,
    )
    db.commit()
    return response


@app.get("/puzzles/sets", response_model=list[PuzzleSetResponse])
def puzzle_sets(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_puzzle_sets(db, current_user.id)


@app.get("/puzzles/sets/{set_id}", response_model=PuzzleSetResponse)
def puzzle_set(
    set_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_puzzle_set(db, current_user.id, set_id)


@app.get("/puzzles/sets/{set_id}/progress", response_model=PuzzleSetProgressResponse)
def puzzle_set_progress(
    set_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_puzzle_set_progress(db, current_user.id, set_id)


@app.post("/puzzles/{puzzle_id}/attempt", response_model=PuzzleAttemptResponse)
def puzzle_attempt(
    puzzle_id: int,
    request: PuzzleAttemptRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = submit_puzzle_attempt(
        db,
        user_id=current_user.id,
        puzzle_id=puzzle_id,
        submitted_answer=request.submitted_answer,
    )
    db.commit()
    return response


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
