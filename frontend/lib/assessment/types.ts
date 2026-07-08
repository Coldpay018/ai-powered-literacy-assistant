export type AssessmentSectionId = "reading" | "typing" | "mcq";
export type AssessmentStatus = "in_progress" | "submitted" | "evaluated";

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
};

export type AssessmentQuestion = {
  attempt_question_id: number;
  section: AssessmentSectionId;
  display_order: number;
  question_type: "reading_mcq" | "copy_typing" | "sentence_completion" | "short_response" | "mcq";
  difficulty: "beginner" | "intermediate" | "advanced";
  passage?: string | null;
  prompt: string;
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
  sections: AssessmentSection[];
  answers: Record<string, AssessmentAnswerValue>;
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
};
