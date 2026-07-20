from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from language_utils import normalize_language as normalize_language_value


UserRole = Literal["learner", "educator", "administrator"]
ExperienceLevel = Literal["Beginner", "Intermediate", "Advanced"]
AgeGroup = Literal["Child", "Teenager", "Adult"]
TranslationSupport = Literal["high", "medium", "minimal"]
SentenceLength = Literal["short", "medium", "long"]
VocabularyComplexity = Literal["simple", "mixed", "advanced"]
GrammarDepth = Literal["light", "moderate", "deep"]
QuestionComplexity = Literal["simple", "mixed", "complex"]
SkillType = Literal["reading", "writing", "comprehension"]
ProficiencyLevel = Literal["beginner", "intermediate", "advanced"]
QuestionSkill = Literal["reading", "writing", "grammar", "vocabulary", "listening", "speaking", "comprehension"]
AssessmentQuestionType = Literal[
    "reading_mcq",
    "copy_typing",
    "sentence_completion",
    "sentence_rearrange",
    "short_response",
    "mcq",
    "fill_in_the_blank",
    "speaking",
    "spoken_answer",
    "reading_aloud",
    "sentence_repetition",
    "pronunciation",
    "spoken_fill_blank",
]
LessonQuestionType = Literal[
    "multiple_choice",
    "fill_in_the_blank",
    "sentence_ordering",
    "reading_comprehension",
    "typing_writing",
    "speaking",
    "listening",
]
ProgressStatus = Literal["not_started", "in_progress", "completed"]
LearningPlanStatus = Literal["pending", "generating", "ready", "failed"]
GeneratedLessonContentStatus = Literal["not_generated", "generating", "ready", "failed"]
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
SUPPORTED_LANGUAGES = {"en", "hi", "ta", "te", "kn"}


def normalize_language(value: str) -> str:
    normalized_value = value.strip().lower()

    if normalized_value in {"hi", "hindi", "हिन्दी"}:
        return "hi"
    if normalized_value in {"ta", "tamil", "தமிழ்"}:
        return "ta"
    if normalized_value in {"te", "telugu", "తెలుగు"}:
        return "te"
    if normalized_value in {"kn", "kannada", "kn-in", "ಕನ್ನಡ"}:
        return "kn"
    if normalized_value in {"en", "english"}:
        return "en"

    raise ValueError("Unsupported language")


def _validate_unique_sequence(items: list[BaseModel], item_name: str) -> None:
    sequence_values = [getattr(item, "sequence_order") for item in items]
    if len(sequence_values) != len(set(sequence_values)):
        raise ValueError(f"{item_name} sequence_order values must be unique")


def _strip_required(value: str) -> str:
    cleaned_value = value.strip()
    if not cleaned_value:
        raise ValueError("Field must not be empty")
    return cleaned_value


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
    translation: Optional[str] = None


class AssessmentTileResponse(BaseModel):
    id: str
    value: str
    translation: Optional[str] = None


class AssessmentQuestionResponse(BaseModel):
    question_id: int
    attempt_question_id: int
    section: str
    display_order: int
    question_type: AssessmentQuestionType
    difficulty: str
    difficulty_rating: Optional[int] = Field(default=None, ge=1, le=5)
    skill: Optional[QuestionSkill] = None
    age_group: Optional[AgeGroup] = None
    experience_level: Optional[ExperienceLevel] = None
    comfortable_language: Optional[str] = None
    learning_language: Optional[str] = None
    tts_text: Optional[str] = None
    tts_read_options: Optional[list[str]] = None
    input_mode: Optional[Literal["letter_tiles", "word_tiles", "voice"]] = None
    shuffled_tiles: Optional[list[AssessmentTileResponse]] = None
    speech_language: Optional[str] = None
    stt_enabled: Optional[bool] = None
    passage: Optional[str] = None
    passage_translation: Optional[str] = None
    prompt: str
    prompt_translation: Optional[str] = None
    instruction_text: Optional[str] = None
    target_text: Optional[str] = None
    target_translation: Optional[str] = None
    translation_language: Optional[str] = None
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
    answered_questions: int = 0
    total_questions: int = 0
    completed_skills: list[QuestionSkill] = Field(default_factory=list)
    current_question: Optional[AssessmentQuestionResponse] = None
    assessment_complete: bool = False
    final_skill_profile: dict[QuestionSkill, int] = Field(default_factory=dict)


class AssessmentAnswerInput(BaseModel):
    attempt_question_id: int
    answer: dict


class AssessmentAnswerRequest(BaseModel):
    attempt_question_id: int
    answer: dict


class AssessmentSpokenAnswerRequest(BaseModel):
    attempt_question_id: int
    spoken_text: str = Field(..., min_length=1)

    @field_validator("spoken_text")
    @classmethod
    def validate_spoken_text(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Required answer missing")
        return cleaned_value


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
    final_skill_profile: dict[QuestionSkill, int] = Field(default_factory=dict)
    difficulty_adjustments: list["AdaptiveDifficultyResponse"] = Field(default_factory=list)


class AssessmentAnswerResponse(BaseModel):
    correct: bool
    skill: QuestionSkill
    question_id: int
    attempt_question_id: int
    difficulty: "AdaptiveDifficultyResponse"
    answered_questions: int
    total_questions: int
    completed_skills: list[QuestionSkill] = Field(default_factory=list)
    next_question: Optional[AssessmentQuestionResponse] = None
    assessment_complete: bool = False
    final_skill_profile: dict[QuestionSkill, int] = Field(default_factory=dict)
    result: Optional[AssessmentResultResponse] = None
    duplicate_submission: bool = False
    feedback: Optional[str] = None
    model_used: Optional[str] = None
    attempt_status: Optional[str] = None


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
    is_unlocked: Optional[bool] = None
    locked: Optional[bool] = None
    is_unlocked: Optional[bool] = None
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
    question_id: int
    id: int
    lesson_id: int
    content_block_id: Optional[int] = None
    question_text: str
    question_type: LessonQuestionType
    skill: SkillType
    difficulty_level: ProficiencyLevel
    difficulty_rating: Optional[int] = Field(default=None, ge=1, le=5)
    age_group: Optional[AgeGroup] = None
    experience_level: Optional[ExperienceLevel] = None
    comfortable_language: Optional[str] = None
    learning_language: Optional[str] = None
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
    question_id: int
    id: int
    lesson_id: int
    content_block_id: Optional[int] = None
    question_text: str
    question_type: LessonQuestionType
    skill: SkillType
    difficulty_level: ProficiencyLevel
    difficulty_rating: Optional[int] = Field(default=None, ge=1, le=5)
    age_group: Optional[AgeGroup] = None
    experience_level: Optional[ExperienceLevel] = None
    comfortable_language: Optional[str] = None
    learning_language: Optional[str] = None
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
    is_unlocked: bool
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
    is_unlocked: bool
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
    lessons: list[LessonSummaryResponse] = Field(default_factory=list)
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
    difficulty_adjustments: list["AdaptiveDifficultyResponse"] = Field(default_factory=list)


class XPTransactionResponse(BaseModel):
    id: int
    amount: int
    source_type: str
    source_id: int
    reward_key: str
    description_key: str
    created_at: datetime

    model_config = {"from_attributes": True}


class XPSummaryResponse(BaseModel):
    total_xp: int
    xp_earned_this_week: int
    recent_transactions: list[XPTransactionResponse] = Field(default_factory=list)
    current_streak: int = Field(..., ge=0)
    longest_streak: int = Field(..., ge=0)
    last_activity_date: Optional[date] = None
    completed_today: bool
    next_streak_message_key: str
    streak_timezone: str


class BadgeResponse(BaseModel):
    badge_key: str
    name_key: str
    description_key: str
    category: str
    icon_key: str
    requirement_type: str
    requirement_value: int
    is_active: bool
    earned_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None


class BadgeSummaryResponse(BaseModel):
    earned_badges: list[BadgeResponse] = Field(default_factory=list)
    locked_badges: list[BadgeResponse] = Field(default_factory=list)
    earned_count: int = Field(..., ge=0)
    total_count: int = Field(..., ge=0)
    recently_earned_badges: list[BadgeResponse] = Field(default_factory=list)


class FlashcardProgressResponse(BaseModel):
    id: int
    user_id: int
    flashcard_id: int
    review_count: int = Field(..., ge=0)
    correct_count: int = Field(..., ge=0)
    incorrect_count: int = Field(..., ge=0)
    mastery_level: int = Field(..., ge=0, le=5)
    review_interval_days: int = Field(..., ge=1)
    next_review_at: Optional[datetime] = None
    last_reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FlashcardResponse(BaseModel):
    id: int
    deck_id: int
    front_text: str
    back_text: str
    example_text: Optional[str] = None
    example_translation: Optional[str] = None
    pronunciation_text: Optional[str] = None
    sequence_order: int = Field(..., gt=0)
    created_at: datetime
    progress: Optional[FlashcardProgressResponse] = None


class FlashcardDeckProgressResponse(BaseModel):
    total_cards: int = Field(..., ge=0)
    due_cards: int = Field(..., ge=0)
    reviewed_cards: int = Field(..., ge=0)
    mastered_cards: int = Field(..., ge=0)


class FlashcardDeckResponse(BaseModel):
    id: int
    user_id: int
    lesson_id: Optional[int] = None
    generated_lesson_plan_id: Optional[int] = None
    title: str
    skill: QuestionSkill
    learning_language: str
    comfortable_language: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    progress: FlashcardDeckProgressResponse
    cards: list[FlashcardResponse] = Field(default_factory=list)


FlashcardReviewOutcome = Literal["need_practice", "know"]


class FlashcardReviewRequest(BaseModel):
    outcome: FlashcardReviewOutcome


class FlashcardReviewResponse(BaseModel):
    flashcard: FlashcardResponse
    progress: FlashcardProgressResponse
    deck_progress: FlashcardDeckProgressResponse
    xp_earned: int = Field(..., ge=0)
    xp_transaction_id: Optional[int] = None


PuzzleType = Literal["jumbled_word", "matching"]


class PuzzleResponse(BaseModel):
    id: int
    puzzle_set_id: int
    puzzle_type: PuzzleType
    instruction_text: str
    instruction_translation: Optional[str] = None
    prompt_text: Optional[str] = None
    prompt_translation: Optional[str] = None
    puzzle_data: dict[str, Any]
    sequence_order: int = Field(..., gt=0)
    created_at: datetime


class PuzzleSetProgressResponse(BaseModel):
    total_puzzles: int = Field(..., ge=0)
    attempted_puzzles: int = Field(..., ge=0)
    correct_puzzles: int = Field(..., ge=0)
    accuracy_percentage: float = Field(..., ge=0, le=100)
    is_complete: bool


class PuzzleSetResponse(BaseModel):
    id: int
    user_id: int
    lesson_id: Optional[int] = None
    generated_lesson_plan_id: Optional[int] = None
    title: str
    skill: QuestionSkill
    difficulty: int = Field(..., ge=1, le=5)
    learning_language: str
    comfortable_language: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    progress: PuzzleSetProgressResponse
    puzzles: list[PuzzleResponse] = Field(default_factory=list)


class PuzzleAttemptRequest(BaseModel):
    submitted_answer: Any


class PuzzleAttemptRecordResponse(BaseModel):
    id: int
    user_id: int
    puzzle_id: int
    submitted_answer: Any
    is_correct: bool
    score: float = Field(..., ge=0, le=1)
    attempt_number: int = Field(..., gt=0)
    completed_at: datetime


class PuzzleAttemptResponse(BaseModel):
    attempt: PuzzleAttemptRecordResponse
    puzzle_set_progress: PuzzleSetProgressResponse
    xp_earned: int = Field(..., ge=0)
    xp_transaction_id: Optional[int] = None


class RecommendedLessonResponse(BaseModel):
    lesson_id: int
    title: str
    description: str
    skill_type: SkillType
    proficiency_level: ProficiencyLevel
    language: str
    course_id: int
    course_title: str
    course_order: int
    module_id: Optional[int] = None
    module_order: int
    sequence_order: int
    lesson_order: int
    estimated_duration_minutes: int
    recommendation_score: float
    recommendation_reason: str
    is_unlocked: bool = True
    current_progress_status: ProgressStatus
    completion_status: ProgressStatus


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


class PersonalizationPerformanceResponse(BaseModel):
    total_lessons: int
    completed_lessons: int
    in_progress_lessons: int
    questions_attempted: int
    correct_answers: int
    incorrect_answers: int
    average_score: float
    best_score: float
    recent_score: float
    current_difficulty: ProficiencyLevel
    last_accessed_at: Optional[datetime] = None


class PersonalizationSkillProfileResponse(BaseModel):
    skill: str
    current_skill: ProficiencyLevel
    current_difficulty: ProficiencyLevel
    content_tone: str
    sentence_length: SentenceLength
    vocabulary_complexity: VocabularyComplexity
    preferred_topics: list[str]
    translation_support: TranslationSupport
    grammar_depth: GrammarDepth
    question_complexity: QuestionComplexity
    example_style: str
    comfortable_language: str
    learning_language: str
    previous_performance: PersonalizationPerformanceResponse


class PersonalizationProfileResponse(BaseModel):
    age: int
    age_group: AgeGroup
    experience_level: ExperienceLevel
    comfortable_language: str
    learning_language: str
    current_skill: ProficiencyLevel
    current_difficulty: ProficiencyLevel
    content_tone: str
    sentence_length: SentenceLength
    vocabulary_complexity: VocabularyComplexity
    preferred_topics: list[str]
    translation_support: TranslationSupport
    grammar_depth: GrammarDepth
    question_complexity: QuestionComplexity
    example_style: str
    previous_performance: PersonalizationPerformanceResponse
    skill_profiles: dict[str, PersonalizationSkillProfileResponse] = Field(default_factory=dict)


class StartingDifficultyResponse(BaseModel):
    user_id: int
    age: int
    age_group: AgeGroup
    experience_level: ExperienceLevel
    comfortable_language: str
    learning_language: str
    requested_skill: Optional[QuestionSkill] = None
    starting_difficulty: int = Field(..., ge=1, le=5)
    skill_difficulties: dict[QuestionSkill, int] = Field(default_factory=dict)
    source: str


class AdaptiveDifficultyResponse(BaseModel):
    skill: QuestionSkill
    previous_difficulty: int = Field(..., ge=1, le=5)
    new_difficulty: int = Field(..., ge=1, le=5)
    correct_streak: int = Field(..., ge=0)
    incorrect_streak: int = Field(..., ge=0)
    rolling_accuracy: float = Field(..., ge=0, le=1)
    adjusted: bool
    reason: str
    updated_at: datetime


class GeneratedLessonPlanAIOutput(BaseModel):
    title: str = Field(..., min_length=1)
    learning_objective: str = Field(..., min_length=1)
    skill: QuestionSkill
    difficulty: int = Field(..., ge=1, le=5)
    sequence_order: int = Field(..., gt=0)
    content_status: GeneratedLessonContentStatus = "not_generated"

    @field_validator("title", "learning_objective")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _strip_required(value)


class GeneratedModuleAIOutput(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    sequence_order: int = Field(..., gt=0)
    lesson_plans: list[GeneratedLessonPlanAIOutput] = Field(..., min_length=1)

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_lesson_sequence(self):
        _validate_unique_sequence(self.lesson_plans, "Lesson plan")
        return self


class GeneratedCourseAIOutput(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    primary_skill: QuestionSkill
    difficulty: int = Field(..., ge=1, le=5)
    sequence_order: int = Field(..., gt=0)
    is_unlocked: bool = False
    completion_status: ProgressStatus = "not_started"
    modules: list[GeneratedModuleAIOutput] = Field(..., min_length=1)

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_module_sequence(self):
        _validate_unique_sequence(self.modules, "Module")
        return self


class LearningPlanAIOutput(BaseModel):
    status: LearningPlanStatus = "ready"
    comfortable_language: str = Field(..., min_length=1)
    learning_language: str = Field(..., min_length=1)
    learner_summary: str = Field(..., min_length=1)
    weakest_skills: list[QuestionSkill] = Field(default_factory=list)
    strongest_skills: list[QuestionSkill] = Field(default_factory=list)
    generation_model: Optional[str] = None
    generation_version: str = Field(..., min_length=1)
    courses: list[GeneratedCourseAIOutput] = Field(..., min_length=1)

    @field_validator("comfortable_language", "learning_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        return normalize_language_value(value)

    @field_validator("learner_summary", "generation_version")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("generation_model")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _strip_required(value)

    @model_validator(mode="after")
    def validate_initial_unlock(self):
        _validate_unique_sequence(self.courses, "Course")
        unlocked_courses = [course for course in self.courses if course.is_unlocked]
        if len(unlocked_courses) != 1:
            raise ValueError("Exactly one generated course must be initially unlocked")

        first_course = min(self.courses, key=lambda course: course.sequence_order)
        if unlocked_courses[0].sequence_order != first_course.sequence_order:
            raise ValueError("The first generated course by sequence_order must be initially unlocked")
        return self


class LearningPlanCreateRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    plan: LearningPlanAIOutput


class GeneratedLessonPlanResponse(BaseModel):
    id: int
    generated_module_id: int
    title: str
    learning_objective: str
    skill: QuestionSkill
    difficulty: int = Field(..., ge=1, le=5)
    sequence_order: int = Field(..., gt=0)
    content_status: GeneratedLessonContentStatus

    model_config = {"from_attributes": True}


class GeneratedModuleResponse(BaseModel):
    id: int
    generated_course_id: int
    title: str
    description: str
    sequence_order: int = Field(..., gt=0)
    lesson_plans: list[GeneratedLessonPlanResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GeneratedCourseResponse(BaseModel):
    id: int
    learning_plan_id: int
    title: str
    description: str
    primary_skill: QuestionSkill
    difficulty: int = Field(..., ge=1, le=5)
    sequence_order: int = Field(..., gt=0)
    is_unlocked: bool
    completion_status: ProgressStatus
    modules: list[GeneratedModuleResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class LearningPlanResponse(BaseModel):
    id: int
    user_id: int
    status: LearningPlanStatus
    comfortable_language: str
    learning_language: str
    learner_summary: str
    weakest_skills: list[QuestionSkill] = Field(default_factory=list)
    strongest_skills: list[QuestionSkill] = Field(default_factory=list)
    generation_model: Optional[str] = None
    generation_version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    generated_at: Optional[datetime] = None
    courses: list[GeneratedCourseResponse] = Field(default_factory=list)
