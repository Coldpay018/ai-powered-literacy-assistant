import type {
  AssessmentAnswerValue,
  AssessmentAttempt,
  AssessmentAnswerResponse,
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

export class AssessmentApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "AssessmentApiError";
    this.code = code;
    this.status = status;
  }
}

export function isAuthenticationError(error: unknown) {
  return error instanceof AuthenticationError;
}

export function isAssessmentApiError(error: unknown) {
  return error instanceof AssessmentApiError;
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

async function parseError(response: Response) {
  let fallbackMessage = "request_failed";
  try {
    const data = (await response.json()) as {
      detail?: string | { code?: string; message?: string };
      code?: string;
      message?: string;
    };
    const detail = data.detail;
    if (typeof detail === "string") {
      fallbackMessage = detail;
      return { code: "REQUEST_FAILED", message: fallbackMessage };
    }
    if (detail && typeof detail === "object") {
      return {
        code: detail.code || "REQUEST_FAILED",
        message: detail.message || fallbackMessage,
      };
    }
    return {
      code: data.code || "REQUEST_FAILED",
      message: data.message || fallbackMessage,
    };
  } catch {
    return { code: "REQUEST_FAILED", message: fallbackMessage };
  }
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
    const error = await parseError(response);

    if (response.status === 401 || response.status === 403) {
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
      }
      throw new AuthenticationError(error.message);
    }

    throw new Error(error.message);
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

export function submitAssessmentAnswer(
  token: string | undefined,
  attemptId: number,
  attemptQuestionId: number,
  answer: AssessmentAnswerValue,
) {
  return request<AssessmentAnswerResponse>(
    `/assessment/attempts/${attemptId}/answer`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        attempt_question_id: attemptQuestionId,
        answer,
      }),
    },
  );
}

export function submitAssessmentSpokenAnswer(
  token: string | undefined,
  attemptId: number,
  attemptQuestionId: number,
  spokenText: string,
) {
  return request<AssessmentAnswerResponse>(
    `/assessment/attempts/${attemptId}/spoken-answer`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        attempt_question_id: attemptQuestionId,
        spoken_text: spokenText,
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
