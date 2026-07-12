import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

import models
from database import Base, SessionLocal, engine
from schema_updates import apply_sqlite_schema_updates


DEMO_COURSE_TITLE = "Reading Adventures"
DEMO_LANGUAGE = "en"
DEMO_SKILL = "comprehension"
DEMO_DIFFICULTY = "beginner"


def _now():
    return datetime.now(timezone.utc)


def _set_attrs(instance, **values):
    for key, value in values.items():
        setattr(instance, key, value)
    if hasattr(instance, "updated_at"):
        instance.updated_at = _now()


def _upsert_module(db: Session, course: models.Course, payload: dict) -> models.CourseModule:
    module = (
        db.query(models.CourseModule)
        .filter(
            models.CourseModule.course_id == course.id,
            models.CourseModule.title == payload["title"],
        )
        .first()
    )
    values = {
        "course_id": course.id,
        "title": payload["title"],
        "description": payload["description"],
        "sequence_order": payload["sequence_order"],
        "is_published": True,
    }
    if module:
        _set_attrs(module, **values)
    else:
        module = models.CourseModule(**values)
        db.add(module)
    db.flush()
    return module


def _upsert_lesson(
    db: Session,
    course: models.Course,
    module: models.CourseModule,
    payload: dict,
) -> models.Lesson:
    lesson = (
        db.query(models.Lesson)
        .filter(
            models.Lesson.course_id == course.id,
            models.Lesson.title == payload["title"],
            models.Lesson.language == DEMO_LANGUAGE,
        )
        .first()
    )
    values = {
        "course_id": course.id,
        "module_id": module.id,
        "title": payload["title"],
        "description": payload["description"],
        "content": payload["content"],
        "skill": DEMO_SKILL,
        "skill_type": DEMO_SKILL,
        "difficulty_level": DEMO_DIFFICULTY,
        "proficiency_level": DEMO_DIFFICULTY,
        "language": DEMO_LANGUAGE,
        "difficulty_order": payload["sequence_order"],
        "estimated_minutes": payload["estimated_minutes"],
        "estimated_duration_minutes": payload["estimated_minutes"],
        "sequence_order": payload["sequence_order"],
        "xp_reward": payload["xp_reward"],
        "is_published": True,
        "is_active": True,
    }
    if lesson:
        _set_attrs(lesson, **values)
    else:
        lesson = models.Lesson(**values)
        db.add(lesson)
    db.flush()
    return lesson


def _upsert_content_block(
    db: Session,
    lesson: models.Lesson,
    payload: dict,
) -> models.LessonContent:
    block = (
        db.query(models.LessonContent)
        .filter(
            models.LessonContent.lesson_id == lesson.id,
            models.LessonContent.sequence_order == payload["sequence_order"],
        )
        .first()
    )
    values = {
        "lesson_id": lesson.id,
        "content_type": payload["content_type"],
        "title": payload["title"],
        "text_content": payload.get("text_content"),
        "content_url": payload.get("content_url"),
        "metadata_json": (
            json.dumps(payload["metadata"], ensure_ascii=False)
            if payload.get("metadata") is not None
            else None
        ),
        "sequence_order": payload["sequence_order"],
        "is_required": payload.get("is_required", True),
    }
    if block:
        _set_attrs(block, **values)
    else:
        block = models.LessonContent(**values)
        db.add(block)
    db.flush()
    return block


def _upsert_question(
    db: Session,
    lesson: models.Lesson,
    quiz_block: models.LessonContent,
    payload: dict,
) -> models.LessonQuestion:
    question = (
        db.query(models.LessonQuestion)
        .filter(
            models.LessonQuestion.lesson_id == lesson.id,
            models.LessonQuestion.sequence_order == payload["sequence_order"],
        )
        .first()
    )
    values = {
        "lesson_id": lesson.id,
        "content_block_id": quiz_block.id,
        "question_text": payload["question_text"],
        "question_type": payload["question_type"],
        "skill": DEMO_SKILL,
        "difficulty_level": DEMO_DIFFICULTY,
        "minimum_age": 9,
        "maximum_age": 11,
        "correct_answer": payload["correct_answer"],
        "explanation": payload["explanation"],
        "sequence_order": payload["sequence_order"],
        "points": payload.get("points", 1),
    }
    if question:
        _set_attrs(question, **values)
    else:
        question = models.LessonQuestion(**values)
        db.add(question)
    db.flush()
    return question


def _upsert_options(db: Session, question: models.LessonQuestion, options: list[dict]) -> None:
    for option_payload in options:
        option = (
            db.query(models.QuestionOption)
            .filter(
                models.QuestionOption.question_id == question.id,
                models.QuestionOption.sequence_order == option_payload["sequence_order"],
            )
            .first()
        )
        values = {
            "question_id": question.id,
            "option_text": option_payload["option_text"],
            "is_correct": option_payload["is_correct"],
            "sequence_order": option_payload["sequence_order"],
        }
        if option:
            _set_attrs(option, **values)
        else:
            db.add(models.QuestionOption(**values))


def _content_blocks(lesson_key: str) -> list[dict]:
    return [
        {
            "sequence_order": 1,
            "content_type": "text",
            "title": "Read the Story",
            "text_content": DEMO_LESSON_TEXT[lesson_key],
        },
        {
            "sequence_order": 2,
            "content_type": "image",
            "title": "Story Illustration",
            "content_url": f"/assets/demo/reading-adventures/{lesson_key}.svg",
        },
        {
            "sequence_order": 3,
            "content_type": "audio",
            "title": "Listen Along",
            "content_url": f"/assets/demo/reading-adventures/{lesson_key}.mp3",
        },
        {
            "sequence_order": 4,
            "content_type": DEMO_PRACTICE[lesson_key]["content_type"],
            "title": DEMO_PRACTICE[lesson_key]["title"],
            "metadata": DEMO_PRACTICE[lesson_key]["metadata"],
        },
        {
            "sequence_order": 5,
            "content_type": "quiz",
            "title": "Check Your Understanding",
            "metadata": {"question_count": len(DEMO_QUESTIONS[lesson_key])},
        },
    ]


DEMO_LESSON_TEXT = {
    "forest-map": (
        "Maya and Arun found a hand-drawn map inside an old library book. "
        "The map showed a forest trail, a stream, and a small stone bridge. "
        "They followed the trail carefully and wrote notes about each landmark."
    ),
    "bridge-clue": (
        "At the stone bridge, Maya noticed three carved stars on the side rail. "
        "Arun remembered that the map also had three stars beside a tree symbol. "
        "They decided the stars were a clue to the next stop."
    ),
    "garden-journal": (
        "Lina kept a garden journal for one week. Each morning, she measured a bean plant "
        "and drew what she saw. By Friday, the plant had two new leaves and a taller stem."
    ),
    "rainy-rescue": (
        "During a rainy afternoon, Dev saw water running toward the classroom doorway. "
        "He asked two friends to help move books to a higher shelf. Then they placed towels "
        "near the door until their teacher arrived."
    ),
}


DEMO_PRACTICE = {
    "forest-map": {
        "content_type": "sequence",
        "title": "Put the Events in Order",
        "metadata": {
            "items": [
                "Maya and Arun found a map.",
                "They followed the forest trail.",
                "They wrote notes about landmarks.",
            ]
        },
    },
    "bridge-clue": {
        "content_type": "matching",
        "title": "Match the Clues",
        "metadata": {
            "pairs": [
                {"left": "three carved stars", "right": "clue on the bridge"},
                {"left": "tree symbol", "right": "mark on the map"},
                {"left": "next stop", "right": "place they wanted to find"},
            ]
        },
    },
    "garden-journal": {
        "content_type": "sequence",
        "title": "Order the Observations",
        "metadata": {
            "items": [
                "Lina measured the plant.",
                "She drew what she saw.",
                "The plant had two new leaves.",
            ]
        },
    },
    "rainy-rescue": {
        "content_type": "matching",
        "title": "Match Action and Reason",
        "metadata": {
            "pairs": [
                {"left": "move books higher", "right": "keep them dry"},
                {"left": "place towels", "right": "slow the water"},
                {"left": "ask friends", "right": "work faster together"},
            ]
        },
    },
}


DEMO_QUESTIONS = {
    "forest-map": [
        {
            "sequence_order": 1,
            "question_type": "mcq",
            "question_text": "Where did Maya and Arun find the map?",
            "correct_answer": "inside an old library book",
            "explanation": "The story says they found the map inside an old library book.",
            "options": [
                ("inside an old library book", True),
                ("under the stone bridge", False),
                ("beside the stream", False),
                ("in Maya's backpack", False),
            ],
        },
        {
            "sequence_order": 2,
            "question_type": "mcq",
            "question_text": "Which landmark was shown on the map?",
            "correct_answer": "a small stone bridge",
            "explanation": "The map showed a forest trail, a stream, and a small stone bridge.",
            "options": [
                ("a small stone bridge", True),
                ("a tall clock tower", False),
                ("a city market", False),
                ("a train station", False),
            ],
        },
        {
            "sequence_order": 3,
            "question_type": "true_false",
            "question_text": "Maya and Arun wrote notes about each landmark.",
            "correct_answer": "true",
            "explanation": "They followed the trail and wrote notes about each landmark.",
            "options": [("True", True), ("False", False)],
        },
    ],
    "bridge-clue": [
        {
            "sequence_order": 1,
            "question_type": "mcq",
            "question_text": "What did Maya notice on the bridge?",
            "correct_answer": "three carved stars",
            "explanation": "Maya noticed three carved stars on the side rail.",
            "options": [
                ("three carved stars", True),
                ("a red ribbon", False),
                ("a broken pencil", False),
                ("two painted arrows", False),
            ],
        },
        {
            "sequence_order": 2,
            "question_type": "mcq",
            "question_text": "Why did Arun think the stars mattered?",
            "correct_answer": "the map also had three stars beside a tree symbol",
            "explanation": "Arun connected the stars on the bridge to the stars on the map.",
            "options": [
                ("the map also had three stars beside a tree symbol", True),
                ("he liked drawing stars", False),
                ("the bridge was very old", False),
                ("the stream was loud", False),
            ],
        },
        {
            "sequence_order": 3,
            "question_type": "short_answer",
            "question_text": "What did Maya and Arun decide the stars were?",
            "correct_answer": "a clue to the next stop",
            "explanation": "They decided the stars were a clue to the next stop.",
            "options": [],
        },
    ],
    "garden-journal": [
        {
            "sequence_order": 1,
            "question_type": "mcq",
            "question_text": "How long did Lina keep her garden journal?",
            "correct_answer": "one week",
            "explanation": "The passage says Lina kept the journal for one week.",
            "options": [
                ("one week", True),
                ("one day", False),
                ("one month", False),
                ("all summer", False),
            ],
        },
        {
            "sequence_order": 2,
            "question_type": "mcq",
            "question_text": "What did Lina measure each morning?",
            "correct_answer": "a bean plant",
            "explanation": "Each morning, she measured a bean plant.",
            "options": [
                ("a bean plant", True),
                ("a garden gate", False),
                ("a flower pot", False),
                ("a rain bucket", False),
            ],
        },
        {
            "sequence_order": 3,
            "question_type": "true_false",
            "question_text": "By Friday, the plant had two new leaves.",
            "correct_answer": "true",
            "explanation": "The passage says the plant had two new leaves by Friday.",
            "options": [("True", True), ("False", False)],
        },
    ],
    "rainy-rescue": [
        {
            "sequence_order": 1,
            "question_type": "mcq",
            "question_text": "What problem did Dev notice?",
            "correct_answer": "water running toward the classroom doorway",
            "explanation": "Dev saw water running toward the classroom doorway.",
            "options": [
                ("water running toward the classroom doorway", True),
                ("a missing notebook", False),
                ("a broken window", False),
                ("a loud bell", False),
            ],
        },
        {
            "sequence_order": 2,
            "question_type": "mcq",
            "question_text": "Why did Dev move the books to a higher shelf?",
            "correct_answer": "to keep them dry",
            "explanation": "Moving the books higher helped protect them from the water.",
            "options": [
                ("to keep them dry", True),
                ("to count them faster", False),
                ("to make room for games", False),
                ("to find a pencil", False),
            ],
        },
        {
            "sequence_order": 3,
            "question_type": "short_answer",
            "question_text": "What did Dev and his friends place near the door?",
            "correct_answer": "towels",
            "explanation": "They placed towels near the door until their teacher arrived.",
            "options": [],
        },
    ],
}


DEMO_COURSE = {
    "title": DEMO_COURSE_TITLE,
    "description": (
        "Development/demo course for ages 9 to 11 focused on beginner reading "
        "comprehension through short stories, sequencing, matching, and quizzes."
    ),
    "skill": DEMO_SKILL,
    "minimum_age": 9,
    "maximum_age": 11,
    "difficulty_level": DEMO_DIFFICULTY,
    "language": DEMO_LANGUAGE,
    "proficiency_level": DEMO_DIFFICULTY,
    "thumbnail": "/assets/demo/reading-adventures/cover.svg",
    "is_published": True,
    "is_active": True,
    "modules": [
        {
            "title": "Map Clues",
            "description": "Use details and sequence clues to follow a short adventure story.",
            "sequence_order": 1,
            "lessons": [
                {
                    "key": "forest-map",
                    "title": "The Forest Map",
                    "description": "Identify story details and order events from a map adventure.",
                    "content": "Read a short passage, review visual and audio supports, sequence events, and answer a quiz.",
                    "sequence_order": 1,
                    "estimated_minutes": 14,
                    "xp_reward": 15,
                },
                {
                    "key": "bridge-clue",
                    "title": "The Bridge Clue",
                    "description": "Connect clues across a passage to understand what characters decide next.",
                    "content": "Read a clue-based passage, match evidence, and answer comprehension questions.",
                    "sequence_order": 2,
                    "estimated_minutes": 15,
                    "xp_reward": 15,
                },
            ],
        },
        {
            "title": "Everyday Evidence",
            "description": "Practice finding evidence and reasons in realistic short passages.",
            "sequence_order": 2,
            "lessons": [
                {
                    "key": "garden-journal",
                    "title": "Lina's Garden Journal",
                    "description": "Use journal details to track changes and answer evidence questions.",
                    "content": "Read an observation passage, order details, and answer a short quiz.",
                    "sequence_order": 1,
                    "estimated_minutes": 13,
                    "xp_reward": 15,
                },
                {
                    "key": "rainy-rescue",
                    "title": "The Rainy Day Rescue",
                    "description": "Understand a problem, actions, and reasons in a classroom story.",
                    "content": "Read a problem-solution passage, match actions to reasons, and answer a quiz.",
                    "sequence_order": 2,
                    "estimated_minutes": 14,
                    "xp_reward": 15,
                },
            ],
        },
    ],
}


def seed_demo_course(db: Session) -> dict[str, int]:
    """Seed one idempotent development/demo course without deleting existing data."""
    course = (
        db.query(models.Course)
        .filter(
            models.Course.title == DEMO_COURSE_TITLE,
            models.Course.language == DEMO_LANGUAGE,
            models.Course.proficiency_level == DEMO_DIFFICULTY,
        )
        .first()
    )
    course_values = {
        key: DEMO_COURSE[key]
        for key in (
            "title",
            "description",
            "skill",
            "minimum_age",
            "maximum_age",
            "difficulty_level",
            "language",
            "proficiency_level",
            "thumbnail",
            "is_published",
            "is_active",
        )
    }
    created_course = 0
    if course:
        _set_attrs(course, **course_values)
    else:
        course = models.Course(**course_values)
        db.add(course)
        created_course = 1
    db.flush()

    module_count = 0
    lesson_count = 0
    content_count = 0
    question_count = 0
    option_count = 0

    for module_payload in DEMO_COURSE["modules"]:
        module = _upsert_module(db, course, module_payload)
        module_count += 1
        for lesson_payload in module_payload["lessons"]:
            lesson = _upsert_lesson(db, course, module, lesson_payload)
            lesson_count += 1

            quiz_block = None
            for block_payload in _content_blocks(lesson_payload["key"]):
                block = _upsert_content_block(db, lesson, block_payload)
                content_count += 1
                if block.content_type == "quiz":
                    quiz_block = block

            if quiz_block is None:
                raise RuntimeError(f"Missing quiz block for lesson {lesson.title}")

            for question_payload in DEMO_QUESTIONS[lesson_payload["key"]]:
                question = _upsert_question(db, lesson, quiz_block, question_payload)
                question_count += 1
                option_payloads = [
                    {
                        "sequence_order": index + 1,
                        "option_text": option_text,
                        "is_correct": is_correct,
                    }
                    for index, (option_text, is_correct) in enumerate(question_payload["options"])
                ]
                _upsert_options(db, question, option_payloads)
                option_count += len(option_payloads)

    db.commit()
    return {
        "created_course": created_course,
        "modules_upserted": module_count,
        "lessons_upserted": lesson_count,
        "content_blocks_upserted": content_count,
        "questions_upserted": question_count,
        "options_upserted": option_count,
    }


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    apply_sqlite_schema_updates(engine)
    session = SessionLocal()
    try:
        result = seed_demo_course(session)
        print(f"Seeded development/demo course: {result}")
    finally:
        session.close()
