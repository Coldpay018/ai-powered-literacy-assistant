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
