import type { LearningPlan, ProgressStatus } from "./types";

const API_BASE_URL = "http://127.0.0.1:8000";

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

export function updateLessonProgress(
  token: string,
  lessonId: number,
  status: ProgressStatus,
  progressPercentage: number,
) {
  return request(`/lessons/${lessonId}/progress`, token, {
    method: "PATCH",
    body: JSON.stringify({
      status,
      progress_percentage: progressPercentage,
    }),
  });
}
