from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from language_utils import normalize_language as normalize_language_value


UserRole = Literal["learner", "educator", "administrator"]
ExperienceLevel = Literal["Beginner", "Intermediate", "Advanced"]
SkillType = Literal["reading", "writing", "comprehension"]
ProficiencyLevel = Literal["beginner", "intermediate", "advanced"]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
ContentType = Literal[
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
]
LessonQuestionType = Literal[
    "mcq",
    "true_false",
    "short_answer",
    "fill_blank",
    "matching",
    "sequence",
]
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
    comfortable_language: str = Field(..., min_length=1)
    learning_language: str = Field(..., min_length=1)
    experience_level: ExperienceLevel
    education_level: str = Field(..., min_length=1)
    role: UserRole

    @field_validator("full_name", "education_level")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be empty")
        return cleaned_value

    @field_validator("comfortable_language", "learning_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_value(value)

    @model_validator(mode="after")
    def validate_language_pair(self):
        if self.comfortable_language == self.learning_language:
            raise ValueError("Comfortable language and learning language must be different")
        return self


class UserResponse(BaseModel):
    id: int
    full_name: str
    age: int
    email: EmailStr
    comfortable_language: Optional[str] = None
    learning_language: Optional[str] = None
    experience_level: Optional[ExperienceLevel] = None
    preferred_language: str
    education_level: str
    role: UserRole
    is_active: bool
    profile_complete: bool
    created_at: datetime

    @field_validator("comfortable_language", "learning_language", "preferred_language")
    @classmethod
    def normalize_response_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        try:
            return normalize_language_value(value)
        except ValueError:
            return "en"

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1)
    age: Optional[int] = Field(default=None, gt=0)
    email: Optional[EmailStr] = None
    comfortable_language: Optional[str] = Field(default=None, min_length=1)
    learning_language: Optional[str] = Field(default=None, min_length=1)
    experience_level: Optional[ExperienceLevel] = None
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

    @field_validator("comfortable_language", "learning_language")
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
    skill: SkillType
    minimum_age: int
    maximum_age: int
    difficulty_level: ProficiencyLevel
    language: str
    proficiency_level: ProficiencyLevel
    thumbnail: Optional[str] = None
    is_published: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("language")
    @classmethod
    def normalize_course_language(cls, value: str) -> str:
        return normalize_language_value(value)

    @field_validator("maximum_age")
    @classmethod
    def validate_course_age_range(cls, value: int, info) -> int:
        minimum_age = info.data.get("minimum_age")
        if minimum_age is not None and minimum_age > value:
            raise ValueError("minimum_age must not exceed maximum_age")
        return value

    model_config = {"from_attributes": True}


class ModuleResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: str
    sequence_order: int
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonResponse(BaseModel):
    id: int
    course_id: int
    module_id: Optional[int] = None
    title: str
    description: str
    content: str
    skill: SkillType
    skill_type: SkillType
    difficulty_level: ProficiencyLevel
    proficiency_level: ProficiencyLevel
    language: str
    difficulty_order: int
    estimated_minutes: int
    estimated_duration_minutes: int
    sequence_order: int
    xp_reward: int
    is_published: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("language")
    @classmethod
    def normalize_lesson_language(cls, value: str) -> str:
        return normalize_language_value(value)

    model_config = {"from_attributes": True}


class LessonContentResponse(BaseModel):
    id: int
    lesson_id: int
    content_type: ContentType
    title: str
    text_content: Optional[str] = None
    content_url: Optional[str] = None
    sequence_order: int
    metadata_json: Optional[str] = None
    is_required: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("content_url")
    @classmethod
    def validate_media_url(cls, value: Optional[str], info) -> Optional[str]:
        content_type = info.data.get("content_type")
        if content_type in {"image", "video", "audio"} and not value:
            raise ValueError("content_url is required for media content blocks")
        return value

    @field_validator("metadata_json")
    @classmethod
    def validate_interactive_payload(cls, value: Optional[str], info) -> Optional[str]:
        content_type = info.data.get("content_type")
        text_content = info.data.get("text_content")
        if content_type in {
            "text",
            "flashcard",
            "matching",
            "drag_drop",
            "fill_blank",
            "sequence",
            "read_aloud",
            "dictation",
            "quiz",
        } and not text_content and not value:
            raise ValueError("text_content or metadata_json is required for this content type")
        return value

    model_config = {"from_attributes": True}


class QuestionOptionResponse(BaseModel):
    id: int
    question_id: int
    option_text: str
    sequence_order: int

    model_config = {"from_attributes": True}


class LessonQuestionResponse(BaseModel):
    id: int
    lesson_id: int
    content_block_id: Optional[int] = None
    question_text: str
    question_type: LessonQuestionType
    skill: SkillType
    difficulty_level: ProficiencyLevel
    minimum_age: int
    maximum_age: int
    explanation: Optional[str] = None
    sequence_order: int
    points: int
    created_at: datetime
    updated_at: datetime
    options: list[QuestionOptionResponse] = Field(default_factory=list)

    @field_validator("maximum_age")
    @classmethod
    def validate_question_age_range(cls, value: int, info) -> int:
        minimum_age = info.data.get("minimum_age")
        if minimum_age is not None and minimum_age > value:
            raise ValueError("minimum_age must not exceed maximum_age")
        return value

    model_config = {"from_attributes": True}


class LearnerQuestionOptionResponse(BaseModel):
    id: int
    option_text: str
    sequence_order: int

    model_config = {"from_attributes": True}


class LearnerLessonQuestionResponse(BaseModel):
    id: int
    lesson_id: int
    content_block_id: Optional[int] = None
    question_text: str
    question_type: LessonQuestionType
    skill: SkillType
    difficulty_level: ProficiencyLevel
    minimum_age: int
    maximum_age: int
    explanation: Optional[str] = None
    sequence_order: int
    points: int
    options: list[LearnerQuestionOptionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class LessonContentBlockResponse(BaseModel):
    id: int
    lesson_id: int
    content_type: ContentType
    title: str
    text_content: Optional[str] = None
    content_url: Optional[str] = None
    sequence_order: int
    metadata: Optional[dict[str, Any]] = None
    is_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LessonSummaryResponse(BaseModel):
    id: int
    course_id: int
    module_id: Optional[int] = None
    title: str
    description: str
    skill: SkillType
    skill_type: SkillType
    difficulty_level: ProficiencyLevel
    proficiency_level: ProficiencyLevel
    language: str
    estimated_minutes: int
    estimated_duration_minutes: int
    sequence_order: int
    difficulty_order: int
    xp_reward: int
    is_published: bool
    is_active: bool

    @field_validator("language")
    @classmethod
    def normalize_summary_language(cls, value: str) -> str:
        return normalize_language_value(value)

    model_config = {"from_attributes": True}


class LessonDetailResponse(LessonSummaryResponse):
    content_blocks: list[LessonContentBlockResponse] = Field(default_factory=list)
    questions: list[LearnerLessonQuestionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LessonNavigationItem(BaseModel):
    id: int
    title: str
    status: ProgressStatus
    locked: bool


class LessonPlayerProgressResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    module_id: Optional[int] = None
    lesson_id: int
    completion_status: ProgressStatus
    status: ProgressStatus
    progress_percentage: float
    last_content_block_id: Optional[int] = None
    questions_attempted: int = 0
    correct_answers: int = 0
    incorrect_answers: int = 0
    current_difficulty: Optional[ProficiencyLevel] = None
    score: float = 0
    best_quiz_score: Optional[float] = None
    attempt_count: int = 0
    time_spent_seconds: int = 0
    time_spent: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LessonPlayerResponse(LessonDetailResponse):
    progress: Optional[LessonPlayerProgressResponse] = None
    locked: bool
    lock_reason: Optional[str] = None
    previous_lesson: Optional[LessonNavigationItem] = None
    next_lesson: Optional[LessonNavigationItem] = None


class ModuleSummaryResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: str
    sequence_order: int
    is_published: bool

    model_config = {"from_attributes": True}


class ModuleDetailResponse(ModuleSummaryResponse):
    lessons: list[LessonSummaryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CourseSummaryResponse(BaseModel):
    id: int
    title: str
    description: str
    skill: SkillType
    minimum_age: int
    maximum_age: int
    difficulty_level: ProficiencyLevel
    proficiency_level: ProficiencyLevel
    language: str
    thumbnail: Optional[str] = None
    is_published: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("language")
    @classmethod
    def normalize_course_summary_language(cls, value: str) -> str:
        return normalize_language_value(value)

    model_config = {"from_attributes": True}


class CourseDetailResponse(CourseSummaryResponse):
    modules: list[ModuleDetailResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LessonAttemptResponse(BaseModel):
    id: int
    user_id: int
    lesson_id: int
    attempt_number: int
    score: float
    total_points: int
    correct_answers: int
    total_questions: int
    time_spent_seconds: int
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LearnerProgressResponse(BaseModel):
    id: int
    user_id: int
    course_id: Optional[int] = None
    module_id: Optional[int] = None
    lesson_id: int
    completion_status: ProgressStatus
    status: ProgressStatus
    progress_percentage: float
    last_content_block_id: Optional[int] = None
    questions_attempted: int = 0
    correct_answers: int = 0
    incorrect_answers: int = 0
    current_difficulty: Optional[ProficiencyLevel] = None
    score: float = 0
    best_quiz_score: Optional[float] = None
    attempt_count: int = 0
    time_spent_seconds: int = 0
    time_spent: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LessonProgressUpdate(BaseModel):
    status: Optional[ProgressStatus] = None
    progress_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    last_content_block_id: Optional[int] = None
    time_spent_seconds: Optional[int] = Field(default=None, ge=0)
    time_spent: Optional[int] = Field(default=None, ge=0)


class LessonQuizSubmitRequest(BaseModel):
    answers: dict[int, str]
    time_spent_seconds: int = Field(default=0, ge=0)


class LessonQuizQuestionResult(BaseModel):
    question_id: int
    correct: bool
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    points_awarded: int
    points: int


class LessonQuizSubmitResponse(BaseModel):
    score: float
    total_points: int
    correct_answers: int
    total_questions: int
    passed: bool
    progress: LearnerProgressResponse
    results: list[LessonQuizQuestionResult]


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
