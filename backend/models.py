from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship, validates

from database import Base
from question_taxonomy import (
    normalize_age_group,
    normalize_difficulty_value,
    normalize_experience_level,
    normalize_question_language,
    normalize_question_skill,
    QUESTION_SKILLS,
)


SKILL_VALUES = ("reading", "writing", "comprehension")
DIFFICULTY_LEVEL_VALUES = ("beginner", "intermediate", "advanced")
LESSON_STATUS_VALUES = ("not_started", "in_progress", "completed")
LEARNING_PLAN_STATUS_VALUES = ("pending", "generating", "ready", "failed")
GENERATED_LESSON_CONTENT_STATUS_VALUES = ("not_generated", "generating", "ready", "failed")
CONTENT_TYPE_VALUES = (
    "text",
    "image",
    "video",
    "audio",
    "flashcard",
    "matching",
    "drag_drop",
    "fill_blank",
    "sequence",
    "read_aloud",
    "dictation",
    "quiz",
)
PUZZLE_TYPE_VALUES = ("jumbled_word", "matching")
LESSON_QUESTION_TYPE_VALUES = (
    "mcq",
    "true_false",
    "short_answer",
    "fill_blank",
    "matching",
    "sequence",
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    comfortable_language = Column(String(50), nullable=True)
    learning_language = Column(String(50), nullable=True)
    experience_level = Column(String(30), nullable=True)
    preferred_language = Column(String(50), nullable=False)
    education_level = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lesson_attempts = relationship("LessonAttempt", back_populates="user")
    lesson_progress_records = relationship("LearnerProgress", back_populates="user")
    learning_plans = relationship("LearningPlan", back_populates="user")
    xp_transactions = relationship("XPTransaction", back_populates="user")
    gamification_summary = relationship("GamificationSummary", back_populates="user", uselist=False)
    streak_summary = relationship("StreakSummary", back_populates="user", uselist=False)
    daily_streak_activities = relationship("DailyStreakActivity", back_populates="user")
    earned_badges = relationship("UserBadge", back_populates="user")
    flashcard_decks = relationship("FlashcardDeck", back_populates="user")
    flashcard_progress_records = relationship("FlashcardProgress", back_populates="user")
    puzzle_sets = relationship("PuzzleSet", back_populates="user")
    puzzle_attempts = relationship("PuzzleAttempt", back_populates="user")

    @property
    def profile_complete(self) -> bool:
        return all(
            isinstance(value, str) and value.strip()
            for value in (
                self.comfortable_language,
                self.learning_language,
                self.experience_level,
            )
        )


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    stable_key = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    version = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    stable_key = Column(String(160), unique=True, index=True, nullable=False)
    assessment_version = Column(String(100), index=True, nullable=False)
    section = Column(String(30), index=True, nullable=False)
    language = Column(String(10), index=True, nullable=False)
    difficulty = Column(String(30), index=True, nullable=False)
    difficulty_rating = Column(Integer, nullable=True, index=True)
    age_group = Column(String(20), nullable=True, index=True)
    experience_level = Column(String(30), nullable=True, index=True)
    comfortable_language = Column(String(10), nullable=True, index=True)
    learning_language = Column(String(10), nullable=True, index=True)
    skill = Column(String(30), nullable=True, index=True)
    question_type = Column(String(50), nullable=False)
    passage = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)
    correct_answer_json = Column(Text, nullable=False)
    scoring_config_json = Column(Text, nullable=True)
    marks = Column(Integer, nullable=False)
    skill_tag = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    @validates("difficulty_rating")
    def _validate_difficulty_rating(self, _key, value):
        if value is None:
            return value
        normalized = normalize_difficulty_value(value)
        if normalized is None:
            raise ValueError("difficulty_rating is required")
        return normalized

    @validates("age_group")
    def _validate_age_group(self, _key, value):
        if value is None:
            return value
        return normalize_age_group(value)

    @validates("experience_level")
    def _validate_experience_level(self, _key, value):
        if value is None:
            return value
        return normalize_experience_level(value)

    @validates("comfortable_language", "learning_language")
    def _validate_question_language(self, _key, value):
        if value is None:
            return value
        return normalize_question_language(value)

    @validates("skill")
    def _validate_skill(self, _key, value):
        if value is None:
            return value
        return normalize_question_skill(value)

    __table_args__ = (
        CheckConstraint("(difficulty_rating IS NULL OR (difficulty_rating >= 1 AND difficulty_rating <= 5))", name="ck_assessment_questions_difficulty_rating_range"),
        CheckConstraint("(age_group IS NULL OR age_group IN ('Child', 'Teenager', 'Adult'))", name="ck_assessment_questions_age_group"),
        CheckConstraint("(experience_level IS NULL OR experience_level IN ('Beginner', 'Intermediate', 'Advanced'))", name="ck_assessment_questions_experience_level"),
        Index("ix_assessment_questions_language_difficulty", "language", "difficulty_rating"),
    )


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    assessment_version = Column(String(100), nullable=False)
    preferred_language = Column(String(10), nullable=False)
    status = Column(String(30), default="in_progress", nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AssessmentAttemptQuestion(Base):
    __tablename__ = "assessment_attempt_questions"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("assessment_attempts.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id"), nullable=False, index=True)
    section = Column(String(30), nullable=False)
    display_order = Column(Integer, nullable=False)
    shuffled_options_json = Column(Text, nullable=True)
    shuffled_tiles_json = Column(Text, nullable=True)
    maximum_marks = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question_once"),
        UniqueConstraint("attempt_id", "display_order", name="uq_attempt_display_order"),
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("assessment_attempts.id"), nullable=False, index=True)
    attempt_question_id = Column(Integer, ForeignKey("assessment_attempt_questions.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("assessment_questions.id"), nullable=False, index=True)
    answer_json = Column(Text, nullable=False)
    normalized_answer_json = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    marks_awarded = Column(Float, default=0, nullable=False)
    maximum_marks = Column(Integer, nullable=False)
    scoring_details_json = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)
    submission_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "attempt_question_id", name="uq_answer_attempt_question"),
        Index("ix_assessment_answers_submission_hash", "attempt_id", "attempt_question_id", "submission_hash"),
    )


class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("assessment_attempts.id"), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assessment_version = Column(String(100), nullable=False)
    reading_score = Column(Float, nullable=False)
    typing_score = Column(Float, nullable=False)
    mcq_score = Column(Float, nullable=False)
    overall_score = Column(Float, nullable=False)
    proficiency_level = Column(String(30), nullable=False)
    final_skill_profile_json = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "assessment_version", name="uq_user_assessment_result"),
    )


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    skill = Column(String(30), default="reading", nullable=False, index=True)
    minimum_age = Column(Integer, default=1, nullable=False)
    maximum_age = Column(Integer, default=120, nullable=False)
    difficulty_level = Column(String(30), default="beginner", nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    proficiency_level = Column(String(30), nullable=False, index=True)
    thumbnail = Column(String(500), nullable=True)
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    modules = relationship("CourseModule", back_populates="course", order_by="CourseModule.sequence_order")
    lessons = relationship("Lesson", back_populates="course")

    __table_args__ = (
        CheckConstraint("minimum_age <= maximum_age", name="ck_courses_age_range"),
        CheckConstraint(f"skill in {SKILL_VALUES}", name="ck_courses_skill"),
        CheckConstraint(f"difficulty_level in {DIFFICULTY_LEVEL_VALUES}", name="ck_courses_difficulty_level"),
        UniqueConstraint("title", "language", "proficiency_level", name="uq_course_title_language_level"),
        Index("ix_courses_language_level_active", "language", "proficiency_level", "is_active"),
        Index("ix_courses_skill_difficulty_published", "skill", "difficulty_level", "is_published"),
    )


class CourseModule(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    sequence_order = Column(Integer, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", order_by="Lesson.sequence_order")

    __table_args__ = (
        UniqueConstraint("course_id", "sequence_order", name="uq_module_course_sequence"),
        UniqueConstraint("course_id", "title", name="uq_module_course_title"),
        Index("ix_modules_course_published_order", "course_id", "is_published", "sequence_order"),
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    skill = Column(String(30), default="reading", nullable=False, index=True)
    skill_type = Column(String(30), nullable=False, index=True)
    difficulty_level = Column(String(30), default="beginner", nullable=False, index=True)
    proficiency_level = Column(String(30), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    difficulty_order = Column(Integer, nullable=False)
    estimated_minutes = Column(Integer, default=15, nullable=False)
    estimated_duration_minutes = Column(Integer, nullable=False)
    sequence_order = Column(Integer, default=1, nullable=False)
    xp_reward = Column(Integer, default=10, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    course = relationship("Course", back_populates="lessons")
    module = relationship("CourseModule", back_populates="lessons")
    content_blocks = relationship("LessonContent", back_populates="lesson", order_by="LessonContent.sequence_order")
    questions = relationship("LessonQuestion", back_populates="lesson", order_by="LessonQuestion.sequence_order")
    attempts = relationship("LessonAttempt", back_populates="lesson")
    progress_records = relationship("LearnerProgress", back_populates="lesson")
    recommendations = relationship("LessonRecommendation", back_populates="lesson")
    flashcard_decks = relationship("FlashcardDeck", back_populates="lesson")
    puzzle_sets = relationship("PuzzleSet", back_populates="lesson")

    __table_args__ = (
        CheckConstraint(f"skill in {SKILL_VALUES}", name="ck_lessons_skill"),
        CheckConstraint(f"difficulty_level in {DIFFICULTY_LEVEL_VALUES}", name="ck_lessons_difficulty_level"),
        CheckConstraint("estimated_minutes > 0", name="ck_lessons_estimated_minutes_positive"),
        CheckConstraint("sequence_order > 0", name="ck_lessons_sequence_order_positive"),
        CheckConstraint("xp_reward >= 0", name="ck_lessons_xp_reward_non_negative"),
        UniqueConstraint("course_id", "title", "language", name="uq_lesson_course_title_language"),
        Index("ix_lessons_recommendation_lookup", "language", "proficiency_level", "skill_type", "is_active"),
        Index("ix_lessons_module_published_order", "module_id", "is_published", "sequence_order"),
    )


class LessonContent(Base):
    __tablename__ = "lesson_content"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    content_type = Column(String(30), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    text_content = Column(Text, nullable=True)
    content_url = Column(String(500), nullable=True)
    sequence_order = Column(Integer, nullable=False)
    metadata_json = Column(Text, nullable=True)
    is_required = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lesson = relationship("Lesson", back_populates="content_blocks")
    questions = relationship("LessonQuestion", back_populates="content_block", order_by="LessonQuestion.sequence_order")

    __table_args__ = (
        CheckConstraint(f"content_type in {CONTENT_TYPE_VALUES}", name="ck_lesson_content_type"),
        CheckConstraint("sequence_order > 0", name="ck_lesson_content_sequence_positive"),
        CheckConstraint(
            "(content_type not in ('text', 'flashcard', 'matching', 'drag_drop', 'fill_blank', 'sequence', 'read_aloud', 'dictation', 'quiz')) or text_content is not null or metadata_json is not null",
            name="ck_lesson_content_interactive_payload",
        ),
        CheckConstraint(
            "(content_type not in ('image', 'video', 'audio')) or content_url is not null",
            name="ck_lesson_content_media_url",
        ),
        UniqueConstraint("lesson_id", "sequence_order", name="uq_lesson_content_sequence"),
        Index("ix_lesson_content_lesson_type_order", "lesson_id", "content_type", "sequence_order"),
    )


class LessonQuestion(Base):
    __tablename__ = "lesson_questions"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    content_block_id = Column(Integer, ForeignKey("lesson_content.id"), nullable=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=False, index=True)
    skill = Column(String(30), nullable=False, index=True)
    difficulty_level = Column(String(30), nullable=False, index=True)
    difficulty_rating = Column(Integer, nullable=True, index=True)
    age_group = Column(String(20), nullable=True, index=True)
    experience_level = Column(String(30), nullable=True, index=True)
    comfortable_language = Column(String(10), nullable=True, index=True)
    learning_language = Column(String(10), nullable=True, index=True)
    minimum_age = Column(Integer, default=1, nullable=False)
    maximum_age = Column(Integer, default=120, nullable=False)
    correct_answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    sequence_order = Column(Integer, nullable=False)
    points = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lesson = relationship("Lesson", back_populates="questions")
    content_block = relationship("LessonContent", back_populates="questions")
    options = relationship("QuestionOption", back_populates="question", order_by="QuestionOption.sequence_order")

    __table_args__ = (
        CheckConstraint(f"question_type in {LESSON_QUESTION_TYPE_VALUES}", name="ck_lesson_questions_type"),
        CheckConstraint(f"skill in {QUESTION_SKILLS}", name="ck_lesson_questions_skill"),
        CheckConstraint(f"difficulty_level in {DIFFICULTY_LEVEL_VALUES}", name="ck_lesson_questions_difficulty_level"),
        CheckConstraint("(difficulty_rating IS NULL OR (difficulty_rating >= 1 AND difficulty_rating <= 5))", name="ck_lesson_questions_difficulty_rating_range"),
        CheckConstraint("(age_group IS NULL OR age_group IN ('Child', 'Teenager', 'Adult'))", name="ck_lesson_questions_age_group"),
        CheckConstraint("(experience_level IS NULL OR experience_level IN ('Beginner', 'Intermediate', 'Advanced'))", name="ck_lesson_questions_experience_level"),
        CheckConstraint("minimum_age <= maximum_age", name="ck_lesson_questions_age_range"),
        CheckConstraint("sequence_order > 0", name="ck_lesson_questions_sequence_positive"),
        CheckConstraint("points >= 0", name="ck_lesson_questions_points_non_negative"),
        UniqueConstraint("lesson_id", "sequence_order", name="uq_lesson_questions_sequence"),
        Index("ix_lesson_questions_lesson_type_order", "lesson_id", "question_type", "sequence_order"),
    )

    @validates("difficulty_rating")
    def _validate_difficulty_rating(self, _key, value):
        if value is None:
            return value
        normalized = normalize_difficulty_value(value)
        if normalized is None:
            raise ValueError("difficulty_rating is required")
        return normalized

    @validates("age_group")
    def _validate_age_group(self, _key, value):
        if value is None:
            return value
        return normalize_age_group(value)

    @validates("experience_level")
    def _validate_experience_level(self, _key, value):
        if value is None:
            return value
        return normalize_experience_level(value)

    @validates("comfortable_language", "learning_language")
    def _validate_question_language(self, _key, value):
        if value is None:
            return value
        return normalize_question_language(value)


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("lesson_questions.id"), nullable=False, index=True)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False)

    question = relationship("LessonQuestion", back_populates="options")

    __table_args__ = (
        CheckConstraint("sequence_order > 0", name="ck_question_options_sequence_positive"),
        UniqueConstraint("question_id", "sequence_order", name="uq_question_options_sequence"),
    )


class LessonAttempt(Base):
    __tablename__ = "lesson_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    score = Column(Float, default=0, nullable=False)
    total_points = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    total_questions = Column(Integer, default=0, nullable=False)
    time_spent_seconds = Column(Integer, default=0, nullable=False)
    submission_hash = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="lesson_attempts")
    lesson = relationship("Lesson", back_populates="attempts")

    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_lesson_attempts_attempt_positive"),
        CheckConstraint("score >= 0", name="ck_lesson_attempts_score_non_negative"),
        CheckConstraint("total_points >= 0", name="ck_lesson_attempts_total_points_non_negative"),
        CheckConstraint("correct_answers >= 0", name="ck_lesson_attempts_correct_answers_non_negative"),
        CheckConstraint("total_questions >= 0", name="ck_lesson_attempts_total_questions_non_negative"),
        CheckConstraint("time_spent_seconds >= 0", name="ck_lesson_attempts_time_non_negative"),
        UniqueConstraint("user_id", "lesson_id", "attempt_number", name="uq_lesson_attempt_user_lesson_number"),
        Index("ix_lesson_attempts_user_lesson_started", "user_id", "lesson_id", "started_at"),
        Index("ix_lesson_attempts_submission_hash", "user_id", "lesson_id", "submission_hash"),
    )


class LearnerProgress(Base):
    __tablename__ = "learner_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    completion_status = Column(String(30), default="not_started", nullable=False, index=True)
    status = Column(String(30), default="not_started", nullable=False, index=True)
    progress_percentage = Column(Float, default=0, nullable=False)
    last_content_block_id = Column(Integer, ForeignKey("lesson_content.id"), nullable=True, index=True)
    questions_attempted = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    incorrect_answers = Column(Integer, default=0, nullable=False)
    current_difficulty = Column(String(30), nullable=True)
    score = Column(Float, default=0, nullable=False)
    best_quiz_score = Column(Float, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    time_spent_seconds = Column(Integer, default=0, nullable=False)
    time_spent = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="lesson_progress_records")
    course = relationship("Course")
    module = relationship("CourseModule")
    lesson = relationship("Lesson", back_populates="progress_records")
    last_content_block = relationship("LessonContent")

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_learner_progress_user_lesson"),
        CheckConstraint(f"status in {LESSON_STATUS_VALUES}", name="ck_learner_progress_status"),
        CheckConstraint(f"completion_status in {LESSON_STATUS_VALUES}", name="ck_learner_progress_completion_status"),
        CheckConstraint("progress_percentage >= 0 and progress_percentage <= 100", name="ck_learner_progress_percentage_range"),
        CheckConstraint("questions_attempted >= 0", name="ck_learner_progress_questions_attempted_non_negative"),
        CheckConstraint("correct_answers >= 0", name="ck_learner_progress_correct_answers_non_negative"),
        CheckConstraint("incorrect_answers >= 0", name="ck_learner_progress_incorrect_answers_non_negative"),
        CheckConstraint("score >= 0", name="ck_learner_progress_score_non_negative"),
        CheckConstraint("best_quiz_score is null or best_quiz_score >= 0", name="ck_learner_progress_best_score_non_negative"),
        CheckConstraint("attempt_count >= 0", name="ck_learner_progress_attempt_count_non_negative"),
        CheckConstraint("time_spent_seconds >= 0", name="ck_learner_progress_time_non_negative"),
        CheckConstraint("time_spent >= 0", name="ck_learner_progress_time_spent_non_negative"),
        Index("ix_learner_progress_user_status", "user_id", "status"),
        Index("ix_learner_progress_user_completion_status", "user_id", "completion_status"),
    )


class LearnerSkillDifficulty(Base):
    __tablename__ = "learner_skill_difficulties"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    skill = Column(String(30), nullable=False, index=True)
    current_difficulty = Column(Integer, default=1, nullable=False)
    correct_streak = Column(Integer, default=0, nullable=False)
    incorrect_streak = Column(Integer, default=0, nullable=False)
    recent_response_history_json = Column(Text, nullable=False, default="[]")
    rolling_accuracy = Column(Float, default=0, nullable=False)
    last_adjustment_reason = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "skill", name="uq_learner_skill_difficulty_user_skill"),
        CheckConstraint(f"skill in {QUESTION_SKILLS}", name="ck_learner_skill_difficulty_skill"),
        CheckConstraint("current_difficulty >= 1 and current_difficulty <= 5", name="ck_learner_skill_difficulty_current_range"),
        CheckConstraint("correct_streak >= 0", name="ck_learner_skill_difficulty_correct_streak_non_negative"),
        CheckConstraint("incorrect_streak >= 0", name="ck_learner_skill_difficulty_incorrect_streak_non_negative"),
        CheckConstraint("rolling_accuracy >= 0 and rolling_accuracy <= 1", name="ck_learner_skill_difficulty_accuracy_range"),
    )


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    reward_key = Column(String(100), nullable=False, index=True)
    description_key = Column(String(120), nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = relationship("User", back_populates="xp_transactions")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_xp_transactions_amount_positive"),
        UniqueConstraint("user_id", "source_type", "source_id", "reward_key", name="uq_xp_transaction_reward_once"),
        Index("ix_xp_transactions_user_created", "user_id", "created_at"),
    )


class GamificationSummary(Base):
    __tablename__ = "gamification_summaries"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    total_xp = Column(Integer, default=0, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="gamification_summary")

    __table_args__ = (
        CheckConstraint("total_xp >= 0", name="ck_gamification_summaries_total_xp_non_negative"),
    )


class StreakSummary(Base):
    __tablename__ = "streak_summaries"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_activity_date = Column(Date, nullable=True)
    streak_started_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="streak_summary")

    __table_args__ = (
        CheckConstraint("current_streak >= 0", name="ck_streak_summaries_current_non_negative"),
        CheckConstraint("longest_streak >= 0", name="ck_streak_summaries_longest_non_negative"),
    )


class DailyStreakActivity(Base):
    __tablename__ = "daily_streak_activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    activity_date = Column(Date, nullable=False, index=True)
    first_qualified_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)

    user = relationship("User", back_populates="daily_streak_activities")

    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_daily_streak_activity_user_date"),
        Index("ix_daily_streak_activities_user_date", "user_id", "activity_date"),
    )


class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    badge_key = Column(String(100), unique=True, nullable=False, index=True)
    name_key = Column(String(160), nullable=False)
    description_key = Column(String(160), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    icon_key = Column(String(50), nullable=False)
    requirement_type = Column(String(50), nullable=False, index=True)
    requirement_value = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    user_badges = relationship("UserBadge", back_populates="badge")

    __table_args__ = (
        CheckConstraint("requirement_value >= 0", name="ck_badges_requirement_value_non_negative"),
    )


class UserBadge(Base):
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False, index=True)
    earned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)

    user = relationship("User", back_populates="earned_badges")
    badge = relationship("Badge", back_populates="user_badges")

    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
        Index("ix_user_badges_user_earned", "user_id", "earned_at"),
    )


class FlashcardDeck(Base):
    __tablename__ = "flashcard_decks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True, index=True)
    generated_lesson_plan_id = Column(Integer, ForeignKey("generated_lesson_plans.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    skill = Column(String(30), nullable=False, index=True)
    learning_language = Column(String(10), nullable=False, index=True)
    comfortable_language = Column(String(10), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="flashcard_decks")
    lesson = relationship("Lesson", back_populates="flashcard_decks")
    generated_lesson_plan = relationship("GeneratedLessonPlan", back_populates="flashcard_decks")
    flashcards = relationship(
        "Flashcard",
        back_populates="deck",
        cascade="all, delete-orphan",
        order_by="Flashcard.sequence_order",
    )

    __table_args__ = (
        CheckConstraint(f"skill in {QUESTION_SKILLS}", name="ck_flashcard_decks_skill"),
        CheckConstraint("learning_language in ('en', 'hi', 'ta', 'te', 'kn')", name="ck_flashcard_decks_learning_language"),
        CheckConstraint("comfortable_language in ('en', 'hi', 'ta', 'te', 'kn')", name="ck_flashcard_decks_comfortable_language"),
        CheckConstraint(
            "lesson_id is not null or generated_lesson_plan_id is not null",
            name="ck_flashcard_decks_has_source",
        ),
        UniqueConstraint("user_id", "lesson_id", "title", name="uq_flashcard_decks_user_lesson_title"),
        UniqueConstraint("user_id", "generated_lesson_plan_id", "title", name="uq_flashcard_decks_user_generated_lesson_title"),
        Index("ix_flashcard_decks_user_active", "user_id", "is_active"),
    )


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("flashcard_decks.id"), nullable=False, index=True)
    front_text = Column(Text, nullable=False)
    back_text = Column(Text, nullable=False)
    example_text = Column(Text, nullable=True)
    example_translation = Column(Text, nullable=True)
    pronunciation_text = Column(Text, nullable=True)
    sequence_order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    deck = relationship("FlashcardDeck", back_populates="flashcards")
    progress_records = relationship("FlashcardProgress", back_populates="flashcard")

    __table_args__ = (
        CheckConstraint("sequence_order > 0", name="ck_flashcards_sequence_positive"),
        UniqueConstraint("deck_id", "sequence_order", name="uq_flashcards_deck_sequence"),
        Index("ix_flashcards_deck_order", "deck_id", "sequence_order"),
    )


class FlashcardProgress(Base):
    __tablename__ = "flashcard_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id"), nullable=False, index=True)
    review_count = Column(Integer, default=0, nullable=False)
    correct_count = Column(Integer, default=0, nullable=False)
    incorrect_count = Column(Integer, default=0, nullable=False)
    mastery_level = Column(Integer, default=0, nullable=False, index=True)
    review_interval_days = Column(Integer, default=1, nullable=False)
    next_review_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="flashcard_progress_records")
    flashcard = relationship("Flashcard", back_populates="progress_records")

    __table_args__ = (
        UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_progress_user_card"),
        CheckConstraint("review_count >= 0", name="ck_flashcard_progress_review_count_non_negative"),
        CheckConstraint("correct_count >= 0", name="ck_flashcard_progress_correct_count_non_negative"),
        CheckConstraint("incorrect_count >= 0", name="ck_flashcard_progress_incorrect_count_non_negative"),
        CheckConstraint("mastery_level >= 0 and mastery_level <= 5", name="ck_flashcard_progress_mastery_range"),
        CheckConstraint("review_interval_days >= 1", name="ck_flashcard_progress_interval_positive"),
        Index("ix_flashcard_progress_user_next_review", "user_id", "next_review_at"),
    )


class PuzzleSet(Base):
    __tablename__ = "puzzle_sets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True, index=True)
    generated_lesson_plan_id = Column(Integer, ForeignKey("generated_lesson_plans.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    skill = Column(String(30), nullable=False, index=True)
    difficulty = Column(Integer, nullable=False, index=True)
    learning_language = Column(String(10), nullable=False, index=True)
    comfortable_language = Column(String(10), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="puzzle_sets")
    lesson = relationship("Lesson", back_populates="puzzle_sets")
    generated_lesson_plan = relationship("GeneratedLessonPlan", back_populates="puzzle_sets")
    puzzles = relationship(
        "Puzzle",
        back_populates="puzzle_set",
        cascade="all, delete-orphan",
        order_by="Puzzle.sequence_order",
    )

    __table_args__ = (
        CheckConstraint(f"skill in {QUESTION_SKILLS}", name="ck_puzzle_sets_skill"),
        CheckConstraint("difficulty >= 1 and difficulty <= 5", name="ck_puzzle_sets_difficulty_range"),
        CheckConstraint("learning_language in ('en', 'hi', 'ta', 'te', 'kn')", name="ck_puzzle_sets_learning_language"),
        CheckConstraint("comfortable_language in ('en', 'hi', 'ta', 'te', 'kn')", name="ck_puzzle_sets_comfortable_language"),
        CheckConstraint(
            "lesson_id is not null or generated_lesson_plan_id is not null",
            name="ck_puzzle_sets_has_source",
        ),
        UniqueConstraint("user_id", "lesson_id", "title", name="uq_puzzle_sets_user_lesson_title"),
        UniqueConstraint("user_id", "generated_lesson_plan_id", "title", name="uq_puzzle_sets_user_generated_lesson_title"),
        Index("ix_puzzle_sets_user_active", "user_id", "is_active"),
    )


class Puzzle(Base):
    __tablename__ = "puzzles"

    id = Column(Integer, primary_key=True, index=True)
    puzzle_set_id = Column(Integer, ForeignKey("puzzle_sets.id"), nullable=False, index=True)
    puzzle_type = Column(String(30), nullable=False, index=True)
    instruction_text = Column(Text, nullable=False)
    instruction_translation = Column(Text, nullable=True)
    prompt_text = Column(Text, nullable=True)
    prompt_translation = Column(Text, nullable=True)
    puzzle_data_json = Column(Text, nullable=False)
    answer_data_json = Column(Text, nullable=False)
    sequence_order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    puzzle_set = relationship("PuzzleSet", back_populates="puzzles")
    attempts = relationship("PuzzleAttempt", back_populates="puzzle")

    __table_args__ = (
        CheckConstraint(f"puzzle_type in {PUZZLE_TYPE_VALUES}", name="ck_puzzles_type"),
        CheckConstraint("sequence_order > 0", name="ck_puzzles_sequence_positive"),
        UniqueConstraint("puzzle_set_id", "sequence_order", name="uq_puzzles_set_sequence"),
        Index("ix_puzzles_set_order", "puzzle_set_id", "sequence_order"),
    )


class PuzzleAttempt(Base):
    __tablename__ = "puzzle_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    puzzle_id = Column(Integer, ForeignKey("puzzles.id"), nullable=False, index=True)
    submitted_answer_json = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, index=True)
    score = Column(Float, default=0, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = relationship("User", back_populates="puzzle_attempts")
    puzzle = relationship("Puzzle", back_populates="attempts")

    __table_args__ = (
        UniqueConstraint("user_id", "puzzle_id", "attempt_number", name="uq_puzzle_attempt_user_puzzle_number"),
        CheckConstraint("score >= 0 and score <= 1", name="ck_puzzle_attempts_score_range"),
        CheckConstraint("attempt_number > 0", name="ck_puzzle_attempts_number_positive"),
        Index("ix_puzzle_attempts_user_puzzle", "user_id", "puzzle_id"),
        Index("ix_puzzle_attempts_user_completed", "user_id", "completed_at"),
    )


# The existing learner_progress table is the lesson-progress table for this
# project. Keep the original class name for API compatibility and expose this
# alias for the Phase 1A learning-structure terminology.
LessonProgress = LearnerProgress


class LessonRecommendation(Base):
    __tablename__ = "lesson_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    recommendation_score = Column(Float, nullable=False)
    recommendation_reason = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    user = relationship("User")
    lesson = relationship("Lesson", back_populates="recommendations")

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", "generated_at", name="uq_recommendation_generation_lesson"),
        Index("ix_recommendations_user_active", "user_id", "is_active"),
    )


class LearningPlan(Base):
    __tablename__ = "learning_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    comfortable_language = Column(String(10), nullable=False, index=True)
    learning_language = Column(String(10), nullable=False, index=True)
    learner_summary = Column(Text, nullable=False)
    weakest_skills = Column(Text, nullable=False, default="[]")
    strongest_skills = Column(Text, nullable=False, default="[]")
    generation_model = Column(String(100), nullable=True)
    generation_version = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    generated_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="learning_plans")
    generated_courses = relationship(
        "GeneratedCourse",
        back_populates="learning_plan",
        cascade="all, delete-orphan",
        order_by="GeneratedCourse.sequence_order",
    )

    __table_args__ = (
        CheckConstraint(f"status in {LEARNING_PLAN_STATUS_VALUES}", name="ck_learning_plans_status"),
        Index("ix_learning_plans_user_status", "user_id", "status"),
        Index("ix_learning_plans_user_languages", "user_id", "comfortable_language", "learning_language"),
        Index(
            "uq_learning_plans_user_active",
            "user_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
        ),
    )


class GeneratedCourse(Base):
    __tablename__ = "generated_courses"

    id = Column(Integer, primary_key=True, index=True)
    learning_plan_id = Column(Integer, ForeignKey("learning_plans.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    primary_skill = Column(String(30), nullable=False, index=True)
    difficulty = Column(Integer, nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False)
    is_unlocked = Column(Boolean, default=False, nullable=False, index=True)
    completion_status = Column(String(30), default="not_started", nullable=False, index=True)

    learning_plan = relationship("LearningPlan", back_populates="generated_courses")
    generated_modules = relationship(
        "GeneratedModule",
        back_populates="generated_course",
        cascade="all, delete-orphan",
        order_by="GeneratedModule.sequence_order",
    )

    __table_args__ = (
        CheckConstraint(f"primary_skill in {QUESTION_SKILLS}", name="ck_generated_courses_primary_skill"),
        CheckConstraint("difficulty >= 1 and difficulty <= 5", name="ck_generated_courses_difficulty_range"),
        CheckConstraint("sequence_order > 0", name="ck_generated_courses_sequence_positive"),
        CheckConstraint(f"completion_status in {LESSON_STATUS_VALUES}", name="ck_generated_courses_completion_status"),
        UniqueConstraint("learning_plan_id", "sequence_order", name="uq_generated_courses_plan_sequence"),
        Index("ix_generated_courses_plan_order", "learning_plan_id", "sequence_order"),
    )


class GeneratedModule(Base):
    __tablename__ = "generated_modules"

    id = Column(Integer, primary_key=True, index=True)
    generated_course_id = Column(Integer, ForeignKey("generated_courses.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    sequence_order = Column(Integer, nullable=False)

    generated_course = relationship("GeneratedCourse", back_populates="generated_modules")
    generated_lesson_plans = relationship(
        "GeneratedLessonPlan",
        back_populates="generated_module",
        cascade="all, delete-orphan",
        order_by="GeneratedLessonPlan.sequence_order",
    )

    __table_args__ = (
        CheckConstraint("sequence_order > 0", name="ck_generated_modules_sequence_positive"),
        UniqueConstraint("generated_course_id", "sequence_order", name="uq_generated_modules_course_sequence"),
        Index("ix_generated_modules_course_order", "generated_course_id", "sequence_order"),
    )


class GeneratedLessonPlan(Base):
    __tablename__ = "generated_lesson_plans"

    id = Column(Integer, primary_key=True, index=True)
    generated_module_id = Column(Integer, ForeignKey("generated_modules.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    learning_objective = Column(Text, nullable=False)
    skill = Column(String(30), nullable=False, index=True)
    difficulty = Column(Integer, nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False)
    content_status = Column(String(30), default="not_generated", nullable=False, index=True)

    generated_module = relationship("GeneratedModule", back_populates="generated_lesson_plans")
    flashcard_decks = relationship("FlashcardDeck", back_populates="generated_lesson_plan")
    puzzle_sets = relationship("PuzzleSet", back_populates="generated_lesson_plan")

    __table_args__ = (
        CheckConstraint(f"skill in {QUESTION_SKILLS}", name="ck_generated_lesson_plans_skill"),
        CheckConstraint("difficulty >= 1 and difficulty <= 5", name="ck_generated_lesson_plans_difficulty_range"),
        CheckConstraint("sequence_order > 0", name="ck_generated_lesson_plans_sequence_positive"),
        CheckConstraint(
            f"content_status in {GENERATED_LESSON_CONTENT_STATUS_VALUES}",
            name="ck_generated_lesson_plans_content_status",
        ),
        UniqueConstraint("generated_module_id", "sequence_order", name="uq_generated_lesson_plans_module_sequence"),
        Index("ix_generated_lesson_plans_module_order", "generated_module_id", "sequence_order"),
    )
