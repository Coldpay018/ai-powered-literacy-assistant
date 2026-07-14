import type {
  CourseDetail,
  LearnerProgress,
  LearningPlan,
  LessonPlayer,
  LessonQuizSubmitResponse,
  ProgressRecord,
  ProgressStatus,
} from "./types";
import { API_BASE_URL } from "@/lib/api/config";

async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let message = "request_failed";
    try {
      const data = (await response.json()) as { detail?: string };
      message = data.detail || message;
    } catch {
      message = "request_failed";
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function getLearningPlan(token: string) {
  return request<LearningPlan>("/learning-plan/me", token);
}

export function getCourseDetail(token: string, courseId: number) {
  return request<CourseDetail>(`/courses/${courseId}`, token);
}

export function updateLessonProgress(
  token: string,
  lessonId: number,
  status: ProgressStatus,
  progressPercentage: number,
  lastContentBlockId?: number,
  timeSpentSeconds?: number,
) {
  return request<LearnerProgress>(`/lessons/${lessonId}/progress`, token, {
    method: "PATCH",
    body: JSON.stringify({
      status,
      progress_percentage: progressPercentage,
      last_content_block_id: lastContentBlockId,
      time_spent_seconds: timeSpentSeconds,
    }),
  });
}

export function getLessonPlayer(token: string, lessonId: number) {
  return request<LessonPlayer>(`/lessons/${lessonId}/player`, token);
}

export function submitLessonQuiz(
  token: string,
  lessonId: number,
  answers: Record<number, string>,
  timeSpentSeconds = 0,
) {
  return request<LessonQuizSubmitResponse>(`/lessons/${lessonId}/quiz/submit`, token, {
    method: "POST",
    body: JSON.stringify({
      answers,
      time_spent_seconds: timeSpentSeconds,
    }),
  });
}

export function getProgressRecords(token: string) {
  return request<ProgressRecord[]>("/progress/me", token);
}
