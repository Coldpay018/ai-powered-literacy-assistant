import type { AssessmentAnswerValue, AssessmentQuestion } from "./types";
import type { TranslationKey } from "@/lib/i18n/translations";

export function isQuestionAnswered(
  question: AssessmentQuestion,
  answer?: AssessmentAnswerValue,
) {
  if (question.question_type === "reading_mcq" || question.question_type === "mcq") {
    return Boolean(answer?.selected_option_id);
  }

  return Boolean(answer?.text?.trim());
}

export function validateQuestion(
  question: AssessmentQuestion,
  answer?: AssessmentAnswerValue,
): TranslationKey | "" {
  if (!isQuestionAnswered(question, answer)) {
    return "assessment.requiredAnswer";
  }

  if (
    question.question_type === "copy_typing" ||
    question.question_type === "sentence_completion" ||
    question.question_type === "sentence_rearrange" ||
    question.question_type === "reading_aloud" ||
    question.question_type === "sentence_repetition" ||
    question.question_type === "pronunciation" ||
    question.question_type === "spoken_fill_blank"
  ) {
    return answer?.text && answer.text.length <= 500
      ? ""
      : "assessment.answerTooLong";
  }

  if (question.question_type === "short_response" || question.question_type === "spoken_answer" || question.question_type === "speaking") {
    return answer?.text && answer.text.length <= 1000
      ? ""
      : "assessment.answerTooLong";
  }

  return "";
}
