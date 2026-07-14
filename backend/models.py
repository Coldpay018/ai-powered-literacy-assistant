from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "attempt_question_id", name="uq_answer_attempt_question"),
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
