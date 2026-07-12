import json

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

import models
from language_utils import normalize_language


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
    return {
        "id": question.id,
        "lesson_id": question.lesson_id,
        "content_block_id": question.content_block_id,
        "question_text": question.question_text,
        "question_type": question.question_type,
        "skill": question.skill,
        "difficulty_level": question.difficulty_level,
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
