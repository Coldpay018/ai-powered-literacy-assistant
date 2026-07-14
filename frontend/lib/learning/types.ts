export type SkillType = "reading" | "writing" | "comprehension";
export type ProficiencyLevel = "beginner" | "intermediate" | "advanced";
export type ProgressStatus = "not_started" | "in_progress" | "completed";

export type RecommendedLesson = {
  lesson_id: number;
  title: string;
  description: string;
  skill_type: SkillType;
  proficiency_level: ProficiencyLevel;
  language: string;
  course_id: number;
  course_title: string;
  course_order: number;
  module_order: number;
  lesson_order: number;
  estimated_duration_minutes: number;
  recommendation_score: number;
  recommendation_reason: string;
  current_progress_status: ProgressStatus;
};

export type LearningPlan = {
  learner_proficiency_level: ProficiencyLevel;
  reading_score: number;
  writing_score: number;
  comprehension_score: number;
  weakest_skill: SkillType;
  recommended_lessons: RecommendedLesson[];
  completion_summary: {
    completed_lessons_count: number;
    in_progress_lessons_count: number;
    total_recommended_lessons: number;
  };
  suggested_next_lesson: RecommendedLesson | null;
};

export type LessonContentBlock = {
  id: number;
  lesson_id: number;
  content_type:
    | "text"
    | "image"
    | "video"
    | "audio"
    | "flashcard"
    | "matching"
    | "drag_drop"
    | "fill_blank"
    | "sequence"
    | "read_aloud"
    | "dictation"
    | "quiz";
  title: string;
  text_content: string | null;
  content_url: string | null;
  sequence_order: number;
  metadata: Record<string, unknown> | null;
  is_required: boolean;
};

export type LessonQuestion = {
  id: number;
  lesson_id: number;
  content_block_id: number | null;
  question_text: string;
  question_type: "mcq" | "true_false" | "short_answer" | "fill_blank" | "matching" | "sequence";
  explanation: string | null;
  sequence_order: number;
  points: number;
  options: Array<{
    id: number;
    option_text: string;
    sequence_order: number;
  }>;
};

export type LearnerProgress = {
  id: number;
  user_id: number;
  course_id: number | null;
  module_id: number | null;
  lesson_id: number;
  completion_status: ProgressStatus;
  status: ProgressStatus;
  progress_percentage: number;
  last_content_block_id: number | null;
  questions_attempted: number;
  correct_answers: number;
  incorrect_answers: number;
  current_difficulty: ProficiencyLevel | null;
  score: number;
  best_quiz_score: number | null;
  attempt_count: number;
  time_spent_seconds: number;
  time_spent: number;
  started_at: string | null;
  completed_at: string | null;
  last_accessed_at: string | null;
};

export type LessonNavigationItem = {
  id: number;
  title: string;
  status: ProgressStatus;
  is_unlocked: boolean;
  locked: boolean;
};

export type LessonPlayer = {
  id: number;
  course_id: number;
  module_id: number | null;
  title: string;
  description: string;
  skill: SkillType;
  skill_type: SkillType;
  difficulty_level: ProficiencyLevel;
  proficiency_level: ProficiencyLevel;
  language: string;
  estimated_minutes: number;
  estimated_duration_minutes: number;
  sequence_order: number;
  difficulty_order: number;
  xp_reward: number;
  content_blocks: LessonContentBlock[];
  questions: LessonQuestion[];
  progress: LearnerProgress | null;
  is_unlocked: boolean;
  locked: boolean;
  lock_reason: string | null;
  previous_lesson: LessonNavigationItem | null;
  next_lesson: LessonNavigationItem | null;
};

export type LessonQuizSubmitResponse = {
  score: number;
  total_points: number;
  correct_answers: number;
  total_questions: number;
  passed: boolean;
  progress: LearnerProgress;
  results: Array<{
    question_id: number;
    correct: boolean;
    correct_answer: string | null;
    explanation: string | null;
    points_awarded: number;
    points: number;
  }>;
};

export type ProgressRecord = LearnerProgress & {
  lesson_title?: string;
  course_title?: string;
  module_title?: string;
};

export type CourseLessonSummary = {
  id: number;
  title: string;
  sequence_order: number;
  module_id: number | null;
};

export type CourseModuleSummary = {
  id: number;
  title: string;
  sequence_order: number;
  lessons: CourseLessonSummary[];
};

export type CourseDetail = {
  id: number;
  title: string;
  modules: CourseModuleSummary[];
  lessons: CourseLessonSummary[];
};
