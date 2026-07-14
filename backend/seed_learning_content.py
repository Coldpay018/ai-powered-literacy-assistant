from sqlalchemy.orm import Session

import models


LEVELS = ["beginner", "intermediate", "advanced"]
SKILLS = {
    "reading": [
        ("Word Clues in Short Sentences", "Practice spotting familiar words and using nearby words for meaning."),
        ("Main Idea in Everyday Texts", "Find the main idea in signs, notes, and short paragraphs."),
        ("Reading Fluency Builder", "Read short passages with repeated patterns to improve speed and confidence."),
        ("Vocabulary from Context", "Use context clues to understand new words while reading."),
    ],
    "writing": [
        ("Sentence Construction Basics", "Build clear sentences with correct word order and punctuation."),
        ("Grammar in Daily Writing", "Practice nouns, verbs, tense, and simple grammar corrections."),
        ("Short Response Practice", "Write complete answers using details from a prompt."),
        ("Paragraph Builder", "Organize related sentences into a focused paragraph."),
    ],
    "comprehension": [
        ("Answering Detail Questions", "Read or listen to short texts and answer direct questions."),
        ("Sequence and Cause", "Identify what happened first, next, and why it happened."),
        ("Inference Practice", "Use clues in a passage to understand ideas that are not stated directly."),
        ("Summarize a Passage", "Choose the most important ideas and summarize them clearly."),
    ],
}


def _set_attrs(instance, **values):
    for key, value in values.items():
        setattr(instance, key, value)


def _has_progress(db: Session, lesson_id: int) -> bool:
    return (
        db.query(models.LearnerProgress.id)
        .filter(models.LearnerProgress.lesson_id == lesson_id)
        .first()
        is not None
    )


def seed_learning_content(db: Session) -> None:
    language = "en"
    for level in LEVELS:
        course = (
            db.query(models.Course)
            .filter(
                models.Course.title == f"{level.title()} English Literacy Path",
                models.Course.language == language,
                models.Course.proficiency_level == level,
            )
            .first()
        )
        if not course:
            course = models.Course(
                title=f"{level.title()} English Literacy Path",
                description=f"Personalized {level} English lessons across reading, writing, and comprehension.",
                language=language,
                proficiency_level=level,
                is_active=True,
            )
            db.add(course)
            db.flush()

        canonical_lessons: list[models.Lesson] = []
        order = 1
        for skill, lesson_templates in SKILLS.items():
            for title, description in lesson_templates:
                lesson_title = f"{level.title()} {title}"
                matches = (
                    db.query(models.Lesson)
                    .filter(
                        models.Lesson.course_id == course.id,
                        models.Lesson.title == lesson_title,
                        models.Lesson.language == language,
                    )
                    .order_by(models.Lesson.created_at, models.Lesson.id)
                    .all()
                )
                lesson = matches[0] if matches else None
                if not lesson:
                    lesson = models.Lesson(
                        course_id=course.id,
                        title=lesson_title,
                        description=f"{description} Designed for {level} learners.",
                        content=(
                            f"Lesson activities for {lesson_title}: guided practice, "
                            "examples, independent exercise, and a short reflection."
                        ),
                        skill_type=skill,
                        proficiency_level=level,
                        language=language,
                        difficulty_order=order,
                        sequence_order=order,
                        estimated_duration_minutes=12 + (LEVELS.index(level) * 4) + (order % 4),
                        is_active=True,
                        is_published=True,
                    )
                    db.add(lesson)
                else:
                    _set_attrs(
                        lesson,
                        course_id=course.id,
                        title=lesson_title,
                        description=f"{description} Designed for {level} learners.",
                        content=(
                            f"Lesson activities for {lesson_title}: guided practice, "
                            "examples, independent exercise, and a short reflection."
                        ),
                        skill_type=skill,
                        proficiency_level=level,
                        language=language,
                        difficulty_order=order,
                        sequence_order=order,
                        estimated_duration_minutes=12 + (LEVELS.index(level) * 4) + (order % 4),
                        is_active=True,
                        is_published=True,
                    )
                canonical_lessons.append(lesson)
                for duplicate in matches[1:]:
                    if not _has_progress(db, duplicate.id):
                        _set_attrs(duplicate, is_active=False, is_published=False)
                order += 1
        active_lessons = (
            db.query(models.Lesson)
            .filter(
                models.Lesson.course_id == course.id,
                models.Lesson.language == language,
                models.Lesson.is_active == True,
                models.Lesson.is_published == True,
            )
            .all()
        )
        canonical_ids = {lesson.id for lesson in canonical_lessons}
        canonical_titles = {lesson.title for lesson in canonical_lessons}
        for stale_lesson in active_lessons:
            if stale_lesson.id in canonical_ids:
                continue
            if stale_lesson.title in canonical_titles:
                continue
            if not _has_progress(db, stale_lesson.id):
                _set_attrs(stale_lesson, is_active=False, is_published=False)
        for index, lesson in enumerate(canonical_lessons, start=1):
            _set_attrs(lesson, sequence_order=index, difficulty_order=index)
    db.commit()


if __name__ == "__main__":
    from database import SessionLocal

    session = SessionLocal()
    try:
        seed_learning_content(session)
    finally:
        session.close()
