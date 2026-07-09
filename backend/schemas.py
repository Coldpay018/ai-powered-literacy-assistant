from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from language_utils import normalize_language as normalize_language_value


UserRole = Literal["learner", "educator", "administrator"]
SkillType = Literal["reading", "writing", "comprehension"]
ProficiencyLevel = Literal["beginner", "intermediate", "advanced"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te"}


def normalize_language(value: str) -> str:
    normalized_value = value.strip().lower()

    if normalized_value in {"hi", "hindi", "हिन्दी"}:
        return "hi"
    if normalized_value in {"ta", "tamil", "தமிழ்"}:
        return "ta"
    if normalized_value in {"te", "telugu", "తెలుగు"}:
        return "te"
    if normalized_value in {"en", "english"}:
        return "en"

    raise ValueError("Unsupported language")


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=1)
    age: int = Field(..., gt=0)
    email: EmailStr
    password: str = Field(..., min_length=8)
    preferred_language: str = Field(..., min_length=1)
    education_level: str = Field(..., min_length=1)
    role: UserRole

    @field_validator("full_name", "education_level")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be empty")
        return cleaned_value

    @field_validator("preferred_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_value(value)


class UserResponse(BaseModel):
    id: int
    full_name: str
    age: int
    email: EmailStr
    preferred_language: str
    education_level: str
    role: UserRole
    is_active: bool
    created_at: datetime

    @field_validator("preferred_language")
    @classmethod
    def normalize_response_language(cls, value: str) -> str:
        try:
            return normalize_language_value(value)
        except ValueError:
            return "en"


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1)
    age: Optional[int] = Field(default=None, gt=0)
    email: Optional[EmailStr] = None
    preferred_language: Optional[str] = Field(default=None, min_length=1)
    education_level: Optional[str] = Field(default=None, min_length=1)

    @field_validator("full_name", "education_level")
    @classmethod
    def validate_optional_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be empty")
        return cleaned_value

    @field_validator("preferred_language")
    @classmethod
    def validate_optional_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        return normalize_language_value(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class AssessmentStatusResponse(BaseModel):
    required: bool
    completed: bool
    has_in_progress_attempt: bool
    attempt_id: Optional[int] = None
    proficiency_level: Optional[str] = None
    reason: Optional[str] = None


class AssessmentOptionResponse(BaseModel):
    id: str
    text: str


class AssessmentQuestionResponse(BaseModel):
    attempt_question_id: int
    section: str
    display_order: int
    question_type: str
    difficulty: str
    passage: Optional[str] = None
    prompt: str
    options: Optional[list[AssessmentOptionResponse]] = None
    marks: int
    skill_tag: str


class AssessmentSectionResponse(BaseModel):
    section: str
    title: str
    questions: list[AssessmentQuestionResponse]


class AssessmentAttemptResponse(BaseModel):
    attempt_id: int
    assessment_title: str
    assessment_version: str
    language: str
    status: str
    started_at: datetime
    sections: list[AssessmentSectionResponse]
    answers: dict[str, dict]


class AssessmentAnswerInput(BaseModel):
    attempt_question_id: int
    answer: dict


class AssessmentAnswersRequest(BaseModel):
    answers: list[AssessmentAnswerInput]


class AssessmentSaveResponse(BaseModel):
    saved: bool
    saved_count: int


class AssessmentResultResponse(BaseModel):
    completed: bool
    assessment_version: str
    completed_at: datetime
    reading_score: float
    typing_score: float
    mcq_score: float
    overall_score: float
    proficiency_level: str


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    language: str
    proficiency_level: ProficiencyLevel
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LessonResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: str
    content: str
    skill_type: SkillType
    proficiency_level: ProficiencyLevel
    language: str
    difficulty_order: int
    estimated_duration_minutes: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LearnerProgressResponse(BaseModel):
    id: int
    user_id: int
    lesson_id: int
    status: ProgressStatus
    progress_percentage: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LessonProgressUpdate(BaseModel):
    status: Optional[ProgressStatus] = None
    progress_percentage: Optional[float] = Field(default=None, ge=0, le=100)


class RecommendedLessonResponse(BaseModel):
    lesson_id: int
    title: str
    description: str
    skill_type: SkillType
    proficiency_level: ProficiencyLevel
    language: str
    estimated_duration_minutes: int
    recommendation_score: float
    recommendation_reason: str
    current_progress_status: ProgressStatus


class CompletionSummaryResponse(BaseModel):
    completed_lessons_count: int
    in_progress_lessons_count: int
    total_recommended_lessons: int


class PersonalizedLearningPlanResponse(BaseModel):
    learner_proficiency_level: ProficiencyLevel
    reading_score: float
    writing_score: float
    comprehension_score: float
    weakest_skill: SkillType
    recommended_lessons: list[RecommendedLessonResponse]
    completion_summary: CompletionSummaryResponse
    suggested_next_lesson: Optional[RecommendedLessonResponse] = None
