import type {
  AssessmentAnswers,
  AssessmentAttempt,
  AssessmentResult,
  AssessmentStatusResponse,
} from "./types";
import { API_BASE_URL } from "@/lib/api/config";

const ACCESS_TOKEN_STORAGE_KEY = "access_token";

export class AuthenticationError extends Error {
  constructor(message = "authentication_required") {
    super(message);
    this.name = "AuthenticationError";
  }
}

export function isAuthenticationError(error: unknown) {
  return error instanceof AuthenticationError;
}

function resolveAccessToken(token?: string) {
  const candidate =
    typeof token === "string" && token.trim()
      ? token
      : typeof window !== "undefined"
        ? window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
        : null;

  const normalizedToken = candidate?.trim();
  if (
    !normalizedToken ||
    normalizedToken === "null" ||
    normalizedToken === "undefined"
  ) {
    throw new AuthenticationError();
  }

  return normalizedToken;
}

async function request<T>(
  path: string,
  token?: string,
  options: RequestInit = {},
): Promise<T> {
  const accessToken = resolveAccessToken(token);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
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

    if (response.status === 401 || response.status === 403) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
      }
      throw new AuthenticationError(message);
    }

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function getAssessmentStatus(token?: string) {
  return request<AssessmentStatusResponse>("/assessment/status", token);
}

export function startAssessment(token?: string) {
  return request<AssessmentAttempt>("/assessment/start", token, {
    method: "POST",
  });
}

export function getCurrentAssessment(token?: string) {
  return request<AssessmentAttempt>("/assessment/current", token);
}

export function saveAssessmentAnswers(
  token: string | undefined,
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

export function submitAssessment(token: string | undefined, attemptId: number) {
  return request<AssessmentResult>(
    `/assessment/attempts/${attemptId}/submit`,
    token,
    { method: "POST" },
  );
}

export function getAssessmentResult(token?: string) {
  return request<AssessmentResult>("/assessment/result", token);
}
