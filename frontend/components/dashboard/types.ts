import type { AssessmentResult, AssessmentStatusResponse } from "@/lib/assessment/types";
import type { LanguageCode } from "@/lib/i18n/types";
import type { TranslationKey } from "@/lib/i18n/translations";
import type { LearningPlan, ProgressRecord, RecommendedLesson } from "@/lib/learning/types";

export type Theme = "light" | "dark";
export type ActiveSection = "dashboard" | "learningActivities" | "progress" | "resources" | "profile";

export type NavItem = {
  id: ActiveSection;
  labelKey: TranslationKey;
};

export type UserProfile = {
  id: number;
  full_name: string;
  age: number;
  email: string;
  comfortable_language: string | null;
  learning_language: string | null;
  experience_level: ExperienceLevel | null;
  education_level: string;
  role: string;
  is_active: boolean;
  profile_complete: boolean;
  created_at: string;
};

export type ExperienceLevel = "Beginner" | "Intermediate" | "Advanced";

export type ProfileForm = {
  full_name: string;
  age: string;
  email: string;
  comfortable_language: LanguageCode | "";
  learning_language: LanguageCode | "";
  experience_level: ExperienceLevel | "";
  education_level: string;
};

export type DashboardPrototypeData = {
  summaryCards: Array<{
    labelKey: TranslationKey;
    value?: string;
    valueKey?: TranslationKey;
    detailKey: TranslationKey;
  }>;
  skillProgress: Array<{ skillKey: TranslationKey; value: number }>;
  recentActivities: TranslationKey[];
  learningActivities: Array<{
    titleKey: TranslationKey;
    descriptionKey: TranslationKey;
    difficultyKey: TranslationKey;
    duration: string;
    category: "reading" | "writing" | "vocabulary" | "comprehension";
  }>;
  resources: Array<{
    titleKey: TranslationKey;
    descriptionKey: TranslationKey;
    type: string;
  }>;
};

export type Translate = (
  key: TranslationKey,
  replacements?: Record<string, string | number>,
) => string;

export type LearningPlanState = {
  learningPlan: LearningPlan | null;
  isLearningPlanLoading: boolean;
  learningPlanError: string;
  updatingLessonId: number | null;
  onRetryLearningPlan: () => void;
  onLessonAction: (lesson: RecommendedLesson) => void;
};

export type ProgressState = {
  progressRecords: ProgressRecord[];
  isProgressLoading: boolean;
  progressError: string;
  onRetryProgress: () => void;
};

export type AssessmentState = {
  assessmentStatus: AssessmentStatusResponse | null;
  assessmentResult: AssessmentResult | null;
  assessmentError: string;
  onStartAssessment: () => void;
  onViewAssessmentResult?: () => void;
};
