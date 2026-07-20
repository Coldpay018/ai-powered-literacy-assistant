import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

import models
from language_utils import normalize_language
from question_taxonomy import (
    clamp_difficulty,
    normalize_age_group,
    normalize_difficulty_value,
    normalize_experience_level,
    normalize_question_language,
    normalize_question_type,
)


def validate_skill_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in models.SKILL_VALUES:
        raise HTTPException(status_code=422, detail="Invalid skill filter")
    return normalized


def validate_difficulty_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in models.DIFFICULTY_LEVEL_VALUES:
        raise HTTPException(status_code=422, detail="Invalid difficulty_level filter")
    return normalized


def validate_language_filter(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return normalize_language(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid language filter") from exc


def list_published_courses(
    db: Session,
    *,
    skill: str | None = None,
    difficulty_level: str | None = None,
    language: str | None = None,
    age: int | None = None,
    proficiency_level: str | None = None,
) -> list[models.Course]:
    query = db.query(models.Course).filter(
        models.Course.is_active == True,
        models.Course.is_published == True,
    )
    if skill:
        query = query.filter(models.Course.skill == skill)
    if difficulty_level:
        query = query.filter(models.Course.difficulty_level == difficulty_level)
    if language:
        query = query.filter(models.Course.language == language)
    if proficiency_level:
        query = query.filter(models.Course.proficiency_level == proficiency_level)
    if age is not None:
        query = query.filter(
            models.Course.minimum_age <= age,
            models.Course.maximum_age >= age,
        )
    return query.order_by(
        models.Course.language,
        models.Course.difficulty_level,
        models.Course.title,
    ).all()


def get_published_course(db: Session, course_id: int) -> models.Course:
    course = (
        db.query(models.Course)
        .options(
            selectinload(models.Course.modules)
            .selectinload(models.CourseModule.lessons),
            selectinload(models.Course.lessons),
        )
        .filter(
            models.Course.id == course_id,
            models.Course.is_active == True,
            models.Course.is_published == True,
        )
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def ordered_course_lessons(course: models.Course) -> list[models.Lesson]:
    ordered_modules = sorted(
        [module for module in course.modules if module.is_published],
        key=lambda module: (
            module.sequence_order if module.sequence_order is not None else 0,
            module.title or "",
            module.id,
        ),
    )
    flattened: list[models.Lesson] = []
    for module in ordered_modules:
        flattened.extend(
            sorted(
                [lesson for lesson in module.lessons if lesson.is_active and lesson.is_published],
                key=lambda lesson: (
                    lesson.sequence_order if lesson.sequence_order is not None else 0,
                    lesson.title or "",
                    lesson.id,
                ),
            )
        )

    standalone_lessons = sorted(
        [
            lesson
            for lesson in course.lessons
            if lesson.is_active and lesson.is_published and lesson.module_id is None
        ],
        key=lambda lesson: (
            lesson.sequence_order if lesson.sequence_order is not None else 0,
            lesson.title or "",
            lesson.id,
        ),
    )
    flattened.extend(standalone_lessons)
    return flattened


def progress_status_map(
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


def sync_progress_metadata(progress: models.LearnerProgress, lesson: models.Lesson) -> None:
    progress.course_id = lesson.course_id
    progress.module_id = lesson.module_id
    progress.current_difficulty = lesson.proficiency_level
    progress.completion_status = progress.status


def get_or_create_lesson_progress(
    db: Session,
    user_id: int,
    lesson: models.Lesson,
) -> models.LearnerProgress:
    progress = (
        db.query(models.LearnerProgress)
        .filter(
            models.LearnerProgress.user_id == user_id,
            models.LearnerProgress.lesson_id == lesson.id,
        )
        .first()
    )
    if not progress:
        progress = models.LearnerProgress(
            user_id=user_id,
            course_id=lesson.course_id,
            module_id=lesson.module_id,
            lesson_id=lesson.id,
            completion_status="not_started",
            status="not_started",
            progress_percentage=0,
            current_difficulty=lesson.proficiency_level,
        )
        db.add(progress)
        db.flush()
    sync_progress_metadata(progress, lesson)
    return progress


def is_lesson_unlocked(
    lesson: models.Lesson,
    ordered_lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> bool:
    index = next((position for position, item in enumerate(ordered_lessons) if item.id == lesson.id), 0)
    if index <= 0:
        return True
    current_progress = progress_by_lesson.get(lesson.id)
    if current_progress and current_progress.status in {"in_progress", "completed"}:
        return True
    previous_lesson = ordered_lessons[index - 1]
    previous_progress = progress_by_lesson.get(previous_lesson.id)
    return previous_progress is not None and previous_progress.status == "completed"


def first_unlocked_lesson(
    ordered_lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> models.Lesson | None:
    for lesson in ordered_lessons:
        if is_lesson_unlocked(lesson, ordered_lessons, progress_by_lesson):
            return lesson
    return ordered_lessons[0] if ordered_lessons else None


def repair_initial_unlock_state(
    db: Session,
    user_id: int,
    ordered_lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> models.LearnerProgress | None:
    if not ordered_lessons:
        return None
    if any(progress.status == "completed" for progress in progress_by_lesson.values()):
        return None
    first_lesson = ordered_lessons[0]
    for lesson in ordered_lessons[1:]:
        progress = progress_by_lesson.get(lesson.id)
        if progress and progress.status in {"in_progress", "completed"}:
            progress.status = "not_started"
            progress.completion_status = "not_started"
            progress.progress_percentage = 0
            progress.started_at = None
            progress.completed_at = None
            db.add(progress)
    progress = progress_by_lesson.get(first_lesson.id)
    if progress is None:
        progress = get_or_create_lesson_progress(db, user_id, first_lesson)
        progress_by_lesson[first_lesson.id] = progress
    else:
        sync_progress_metadata(progress, first_lesson)
        db.add(progress)
    return progress


def start_unlocked_lesson_progress(
    db: Session,
    user_id: int,
    lesson: models.Lesson,
) -> models.LearnerProgress:
    progress = get_or_create_lesson_progress(db, user_id, lesson)
    now = datetime.now(timezone.utc)
    progress.last_accessed_at = now
    if progress.status == "not_started":
        progress.status = "in_progress"
        progress.completion_status = "in_progress"
        progress.started_at = progress.started_at or now
        progress.progress_percentage = max(progress.progress_percentage, 1)
    db.add(progress)
    return progress


def navigation_item(
    lesson: models.Lesson | None,
    ordered_lessons: list[models.Lesson],
    progress_by_lesson: dict[int, models.LearnerProgress],
) -> dict | None:
    if lesson is None:
        return None
    progress = progress_by_lesson.get(lesson.id)
    unlocked = is_lesson_unlocked(lesson, ordered_lessons, progress_by_lesson)
    return {
        "id": lesson.id,
        "title": lesson.title,
        "status": progress.status if progress else "not_started",
        "is_unlocked": unlocked,
        "locked": not unlocked,
    }


def list_published_modules(db: Session, course_id: int) -> list[models.CourseModule]:
    course = get_published_course(db, course_id)
    published_modules = [module for module in course.modules if module.is_published]
    return sorted(published_modules, key=lambda item: item.sequence_order)


def get_published_module(db: Session, module_id: int) -> models.CourseModule:
    module = (
        db.query(models.CourseModule)
        .options(selectinload(models.CourseModule.lessons))
        .join(models.Course)
        .filter(
            models.CourseModule.id == module_id,
            models.CourseModule.is_published == True,
            models.Course.is_active == True,
            models.Course.is_published == True,
        )
        .first()
    )
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


def get_published_lesson(db: Session, lesson_id: int) -> models.Lesson:
    lesson = (
        db.query(models.Lesson)
        .options(
            selectinload(models.Lesson.content_blocks),
            selectinload(models.Lesson.questions).selectinload(models.LessonQuestion.options),
            selectinload(models.Lesson.course),
            selectinload(models.Lesson.module),
            selectinload(models.Lesson.course).selectinload(models.Course.modules).selectinload(models.CourseModule.lessons),
            selectinload(models.Lesson.course).selectinload(models.Course.lessons),
        )
        .filter(
            models.Lesson.id == lesson_id,
            models.Lesson.is_active == True,
            models.Lesson.is_published == True,
        )
        .first()
    )
    if (
        not lesson
        or not lesson.course
        or not lesson.course.is_active
        or not lesson.course.is_published
        or (lesson.module is not None and not lesson.module.is_published)
    ):
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


def serialize_course_summary(course: models.Course) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "skill": course.skill,
        "minimum_age": course.minimum_age,
        "maximum_age": course.maximum_age,
        "difficulty_level": course.difficulty_level,
        "proficiency_level": course.proficiency_level,
        "language": course.language,
        "thumbnail": course.thumbnail,
        "is_published": course.is_published,
        "is_active": course.is_active,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }


def serialize_module_summary(module: models.CourseModule) -> dict:
    return {
        "id": module.id,
        "course_id": module.course_id,
        "title": module.title,
        "description": module.description,
        "sequence_order": module.sequence_order,
        "is_published": module.is_published,
    }


def serialize_lesson_summary(lesson: models.Lesson) -> dict:
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "module_id": lesson.module_id,
        "title": lesson.title,
        "description": lesson.description,
        "skill": lesson.skill,
        "skill_type": lesson.skill_type,
        "difficulty_level": lesson.difficulty_level,
        "proficiency_level": lesson.proficiency_level,
        "language": lesson.language,
        "estimated_minutes": lesson.estimated_minutes,
        "estimated_duration_minutes": lesson.estimated_duration_minutes,
        "sequence_order": lesson.sequence_order,
        "difficulty_order": lesson.difficulty_order,
        "xp_reward": lesson.xp_reward,
        "is_published": lesson.is_published,
        "is_active": lesson.is_active,
    }


def serialize_content_block(content: models.LessonContent) -> dict:
    metadata = None
    if content.metadata_json:
        try:
            metadata = json.loads(content.metadata_json)
        except json.JSONDecodeError:
            metadata = None

    return {
        "id": content.id,
        "lesson_id": content.lesson_id,
        "content_type": content.content_type,
        "title": content.title,
        "text_content": content.text_content,
        "content_url": content.content_url,
        "sequence_order": content.sequence_order,
        "metadata": metadata,
        "is_required": content.is_required,
        "created_at": content.created_at,
        "updated_at": content.updated_at,
    }


def serialize_question_option(option: models.QuestionOption) -> dict:
    return {
        "id": option.id,
        "option_text": option.option_text,
        "sequence_order": option.sequence_order,
    }


def serialize_lesson_question(question: models.LessonQuestion) -> dict:
    try:
        normalized_question_type = normalize_question_type(question.question_type)
    except ValueError:
        normalized_question_type = question.question_type
    try:
        normalized_difficulty = clamp_difficulty(normalize_difficulty_value(question.difficulty_rating) or 1)
    except ValueError:
        normalized_difficulty = 1
    try:
        normalized_age_group = normalize_age_group(question.age_group) if question.age_group else None
    except ValueError:
        normalized_age_group = None
    try:
        normalized_experience_level = normalize_experience_level(question.experience_level) if question.experience_level else None
    except ValueError:
        normalized_experience_level = None
    try:
        normalized_comfortable_language = (
            normalize_question_language(question.comfortable_language)
            if question.comfortable_language
            else None
        )
    except ValueError:
        normalized_comfortable_language = None
    try:
        normalized_learning_language = (
            normalize_question_language(question.learning_language)
            if question.learning_language
            else None
        )
    except ValueError:
        normalized_learning_language = None
    return {
        "id": question.id,
        "question_id": question.id,
        "lesson_id": question.lesson_id,
        "content_block_id": question.content_block_id,
        "question_text": question.question_text,
        "question_type": normalized_question_type,
        "skill": question.skill,
        "difficulty_level": question.difficulty_level,
        "difficulty_rating": normalized_difficulty,
        "age_group": normalized_age_group,
        "experience_level": normalized_experience_level,
        "comfortable_language": normalized_comfortable_language,
        "learning_language": normalized_learning_language,
        "minimum_age": question.minimum_age,
        "maximum_age": question.maximum_age,
        "explanation": question.explanation,
        "sequence_order": question.sequence_order,
        "points": question.points,
        "options": [
            serialize_question_option(option)
            for option in sorted(question.options, key=lambda item: item.sequence_order)
        ],
    }


def serialize_module_detail(module: models.CourseModule) -> dict:
    published_lessons = [
        lesson
        for lesson in module.lessons
        if lesson.is_active and lesson.is_published
    ]
    return {
        **serialize_module_summary(module),
        "lessons": [
            serialize_lesson_summary(lesson)
            for lesson in sorted(published_lessons, key=lambda item: item.sequence_order)
        ],
        "created_at": module.created_at,
        "updated_at": module.updated_at,
    }


def serialize_course_detail(course: models.Course) -> dict:
    published_modules = [module for module in course.modules if module.is_published]
    return {
        **serialize_course_summary(course),
        "modules": [
            serialize_module_detail(module)
            for module in sorted(published_modules, key=lambda item: item.sequence_order)
        ],
        "lessons": [serialize_lesson_summary(lesson) for lesson in ordered_course_lessons(course)],
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }


def serialize_lesson_detail(lesson: models.Lesson) -> dict:
    return {
        **serialize_lesson_summary(lesson),
        "content_blocks": [
            serialize_content_block(content)
            for content in sorted(lesson.content_blocks, key=lambda item: item.sequence_order)
        ],
        "questions": [
            serialize_lesson_question(question)
            for question in sorted(lesson.questions, key=lambda item: item.sequence_order)
        ],
        "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
    }
