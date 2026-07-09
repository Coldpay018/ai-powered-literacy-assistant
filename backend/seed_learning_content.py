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

        order = 1
        for skill, lesson_templates in SKILLS.items():
            for title, description in lesson_templates:
                lesson_title = f"{level.title()} {title}"
                exists = (
                    db.query(models.Lesson)
                    .filter(
                        models.Lesson.course_id == course.id,
                        models.Lesson.title == lesson_title,
                        models.Lesson.language == language,
                    )
                    .first()
                )
                if exists:
                    order += 1
                    continue

                db.add(
                    models.Lesson(
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
                        estimated_duration_minutes=12 + (LEVELS.index(level) * 4) + (order % 4),
                        is_active=True,
                    )
                )
                order += 1
    db.commit()


if __name__ == "__main__":
    from database import SessionLocal

    session = SessionLocal()
    try:
        seed_learning_content(session)
    finally:
        session.close()
