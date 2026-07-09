from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    preferred_language = Column(String(50), nullable=False)
    education_level = Column(String(100), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
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
    language = Column(String(10), nullable=False, index=True)
    proficiency_level = Column(String(30), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    lessons = relationship("Lesson", back_populates="course")

    __table_args__ = (
        UniqueConstraint("title", "language", "proficiency_level", name="uq_course_title_language_level"),
        Index("ix_courses_language_level_active", "language", "proficiency_level", "is_active"),
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    skill_type = Column(String(30), nullable=False, index=True)
    proficiency_level = Column(String(30), nullable=False, index=True)
    language = Column(String(10), nullable=False, index=True)
    difficulty_order = Column(Integer, nullable=False)
    estimated_duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    course = relationship("Course", back_populates="lessons")
    progress_records = relationship("LearnerProgress", back_populates="lesson")
    recommendations = relationship("LessonRecommendation", back_populates="lesson")

    __table_args__ = (
        UniqueConstraint("course_id", "title", "language", name="uq_lesson_course_title_language"),
        Index("ix_lessons_recommendation_lookup", "language", "proficiency_level", "skill_type", "is_active"),
    )


class LearnerProgress(Base):
    __tablename__ = "learner_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    status = Column(String(30), default="not_started", nullable=False, index=True)
    progress_percentage = Column(Float, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    lesson = relationship("Lesson", back_populates="progress_records")

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_learner_progress_user_lesson"),
        Index("ix_learner_progress_user_status", "user_id", "status"),
    )


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
