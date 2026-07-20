export type AssessmentSectionId = "reading" | "typing" | "mcq";
export type AssessmentStatus = "in_progress" | "submitted" | "evaluated";
export type AssessmentQuestionType =
  | "reading_mcq"
  | "copy_typing"
  | "sentence_completion"
  | "sentence_rearrange"
  | "short_response"
  | "mcq"
  | "fill_in_the_blank"
  | "speaking"
  | "spoken_answer"
  | "reading_aloud"
  | "sentence_repetition"
  | "pronunciation"
  | "spoken_fill_blank";
export type AssessmentSkill =
  | "reading"
  | "writing"
  | "vocabulary"
  | "grammar"
  | "listening"
  | "speaking"
  | "comprehension";

export type AssessmentStatusResponse = {
  required: boolean;
  completed: boolean;
  has_in_progress_attempt: boolean;
  attempt_id: number | null;
  proficiency_level: string | null;
  reason?: string | null;
};

export type AssessmentOption = {
  id: string;
  text: string;
  translation?: string | null;
};

export type AssessmentTile = {
  id: string;
  value: string;
  translation?: string | null;
};

export type AssessmentQuestion = {
  attempt_question_id: number;
  question_id: number;
  section: AssessmentSectionId;
  display_order: number;
  question_type: AssessmentQuestionType;
  difficulty: "beginner" | "intermediate" | "advanced";
  difficulty_rating?: number | null;
  skill?: AssessmentSkill | null;
  age_group?: "Child" | "Teenager" | "Adult" | null;
  experience_level?: "Beginner" | "Intermediate" | "Advanced" | null;
  comfortable_language?: string | null;
  learning_language?: string | null;
  tts_text?: string | null;
  tts_read_options?: string[] | null;
  input_mode?: "letter_tiles" | "word_tiles" | "voice" | null;
  shuffled_tiles?: AssessmentTile[] | null;
  speech_language?: string | null;
  stt_enabled?: boolean | null;
  translation_language?: string | null;
  passage?: string | null;
  passage_translation?: string | null;
  prompt: string;
  prompt_translation?: string | null;
  instruction_text?: string | null;
  target_text?: string | null;
  target_translation?: string | null;
  options?: AssessmentOption[] | null;
  marks: number;
  skill_tag: string;
};

export type AssessmentSection = {
  section: AssessmentSectionId;
  title: string;
  questions: AssessmentQuestion[];
};

export type AssessmentAttempt = {
  attempt_id: number;
  assessment_title: string;
  assessment_version: string;
  language: string;
  status: AssessmentStatus;
  started_at: string;
  answered_questions: number;
  total_questions: number;
  completed_skills: AssessmentSkill[];
  current_question: AssessmentQuestion | null;
  assessment_complete: boolean;
  final_skill_profile: Record<AssessmentSkill, number>;
};

export type AssessmentAnswerValue = {
  selected_option_id?: string;
  text?: string;
};

export type AssessmentAnswers = Record<number, AssessmentAnswerValue>;

export type AssessmentResult = {
  completed: boolean;
  assessment_version: string;
  completed_at: string;
  reading_score: number;
  typing_score: number;
  mcq_score: number;
  overall_score: number;
  proficiency_level: "beginner" | "intermediate" | "advanced";
  final_skill_profile: Record<AssessmentSkill, number>;
  difficulty_adjustments?: Array<{
    skill: AssessmentSkill;
    previous_difficulty: number;
    new_difficulty: number;
    correct_streak: number;
    incorrect_streak: number;
    rolling_accuracy: number;
    adjusted: boolean;
    reason: string;
    updated_at: string;
  }>;
};

export type AssessmentAnswerResponse = {
  correct: boolean;
  skill: AssessmentSkill;
  question_id: number;
  attempt_question_id: number;
  difficulty: {
    skill: AssessmentSkill;
    previous_difficulty: number;
    new_difficulty: number;
    correct_streak: number;
    incorrect_streak: number;
    rolling_accuracy: number;
    adjusted: boolean;
    reason: string;
    updated_at: string;
  };
  answered_questions: number;
  total_questions: number;
  completed_skills: AssessmentSkill[];
  next_question: AssessmentQuestion | null;
  assessment_complete: boolean;
  final_skill_profile: Record<AssessmentSkill, number>;
  result: AssessmentResult | null;
  duplicate_submission: boolean;
  feedback?: string | null;
  model_used?: string | null;
  attempt_status?: string | null;
};
