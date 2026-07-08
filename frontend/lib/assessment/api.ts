import type {
  AssessmentAnswers,
  AssessmentAttempt,
  AssessmentResult,
  AssessmentStatusResponse,
} from "./types";

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

export function getAssessmentStatus(token: string) {
  return request<AssessmentStatusResponse>("/assessment/status", token);
}

export function startAssessment(token: string) {
  return request<AssessmentAttempt>("/assessment/start", token, {
    method: "POST",
  });
}

export function getCurrentAssessment(token: string) {
  return request<AssessmentAttempt>("/assessment/current", token);
}

export function saveAssessmentAnswers(
  token: string,
  attemptId: number,
  answers: AssessmentAnswers,
) {
  return request<{ saved: boolean; saved_count: number }>(
    `/assessment/attempts/${attemptId}/answers`,
    token,
    {
      method: "PUT",
      body: JSON.stringify({
        answers: Object.entries(answers).map(([attemptQuestionId, answer]) => ({
          attempt_question_id: Number(attemptQuestionId),
          answer,
        })),
      }),
    },
  );
}

export function submitAssessment(token: string, attemptId: number) {
  return request<AssessmentResult>(
    `/assessment/attempts/${attemptId}/submit`,
    token,
    { method: "POST" },
  );
}

export function getAssessmentResult(token: string) {
  return request<AssessmentResult>("/assessment/result", token);
}
