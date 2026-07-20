import type { LessonContentBlock } from "@/lib/learning/types";
import type { AssessmentQuestion } from "@/lib/assessment/types";

import type { TranslationKey } from "@/lib/i18n/translations";
import type { SpeechLanguageCode } from "./language";

const INSTRUCTION_TITLES = /(instruction|instructions|explanation|overview|objective|guide|help|summary|note|reflection)/i;
const BLANK_LABELS: Record<SpeechLanguageCode, string> = {
  en: "blank",
  hi: "रिक्त स्थान",
  ta: "காலியிடம்",
  te: "ఖాళీ",
  kn: "ಖಾಲಿ ಜಾಗ",
};
const COMPLETE_SENTENCE_PROMPTS: Record<SpeechLanguageCode, string> = {
  en: "Complete the sentence.",
  hi: "वाक्य पूरा करें।",
  ta: "வாக்கியத்தை முடிக்கவும்.",
  te: "వాక్యాన్ని పూర్తి చేయండి.",
  kn: "ವಾಕ್ಯವನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ.",
};
const REARRANGE_SENTENCE_PROMPTS: Record<SpeechLanguageCode, string> = {
  en: "Arrange the words to make a sentence.",
  hi: "शब्दों को सही क्रम में लगाकर वाक्य बनाइए।",
  ta: "சொற்களை சரியான வரிசையில் அமைத்து ஒரு வாக்கியத்தை உருவாக்கவும்.",
  te: "పదాలను సరైన క్రమంలో అమర్చి వాక్యం రూపొందించండి.",
  kn: "ಪದಗಳನ್ನು ಸರಿಯಾದ ಕ್ರಮದಲ್ಲಿ ಇಟ್ಟು ವಾಕ್ಯವನ್ನು ರಚಿಸಿ.",
};

function stringifyItems(items: unknown): string[] {
  return Array.isArray(items) ? items.filter((item): item is string => typeof item === "string") : [];
}

function stringifyPairs(value: unknown): Array<{ left: string; right: string }> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is { left: string; right: string } =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as { left?: unknown }).left === "string" &&
      typeof (item as { right?: unknown }).right === "string",
  );
}

function normalizeSpokenText(text: string) {
  return text
    .replace(/\s+/g, " ")
    .replace(/\s+([,.;:!?])/g, "$1")
    .replace(/([,.;:!?])(?!\s|$)/g, "$1 ")
    .trim();
}

export function sanitizeSpeechText(
  text: string,
  language?: string | null,
  options: { blankStyle?: "space" | "comma" } = {},
) {
  const speechLanguage = (language || "en").toLowerCase().split("-")[0] as SpeechLanguageCode;
  const blankLabel = BLANK_LABELS[speechLanguage] || BLANK_LABELS.en;
  const replacement = options.blankStyle === "comma" ? `, ${blankLabel}` : ` ${blankLabel} `;
  return normalizeSpokenText(
    (text || "")
      .replace(/_{2,}/g, replacement)
      .replace(/\r\n/g, " ")
      .replace(/\r/g, " ")
      .replace(/\n/g, " "),
  );
}

export type SpeechSegment = {
  text: string;
  language?: string | null;
};

export type TtsContentConfig = {
  text: string;
  language: string | null;
  label: TranslationKey;
};

export type AssessmentSpeechContent = {
  segments: SpeechSegment[];
  missingQuestionText: boolean;
};

export function buildLessonSpeechConfig(
  block: LessonContentBlock,
  comfortableLanguage?: string | null,
  learningLanguage?: string | null,
): TtsContentConfig | null {
  const title = block.title.trim();
  const titleIsInstruction = INSTRUCTION_TITLES.test(title);
  const baseLanguage = titleIsInstruction ? comfortableLanguage || learningLanguage : learningLanguage || comfortableLanguage;

  if (block.content_type === "image") {
    return null;
  }

  if (block.content_type === "audio") {
    const speechText = block.text_content?.trim();
    if (!speechText) {
      return null;
    }
    return {
      text: speechText,
      language: baseLanguage || null,
      label: "tts.replay",
    };
  }

  if (block.content_type === "sequence") {
    const items = stringifyItems(block.metadata?.items);
    if (!items.length) {
      return null;
    }
    return {
      text: items.join(". "),
      language: learningLanguage || comfortableLanguage || null,
      label: "tts.readSequence",
    };
  }

  if (block.content_type === "matching") {
    const pairs = stringifyPairs(block.metadata?.pairs);
    if (!pairs.length) {
      return null;
    }
    return {
      text: pairs.map((pair) => `${pair.left}. ${pair.right}`).join(" "),
      language: learningLanguage || comfortableLanguage || null,
      label: "tts.replayExamples",
    };
  }

  const speechText = block.text_content?.trim();
  if (!speechText) {
    return null;
  }

  return {
    text: speechText,
    language: baseLanguage || null,
    label: titleIsInstruction ? "tts.readExplanation" : "tts.readContent",
  };
}

export function buildAssessmentReadAllSegments(question: AssessmentQuestion): AssessmentSpeechContent {
  const learningLanguage = question.speech_language || question.learning_language || question.comfortable_language || "en";
  const segments: SpeechSegment[] = [];
  let missingQuestionText = false;

  const addSegment = (text: string | null | undefined, language?: string | null) => {
    if (typeof text !== "string" || !text.trim()) {
      missingQuestionText = true;
      return;
    }
    const cleaned = sanitizeSpeechText(text, language || undefined);
    if (!cleaned) {
      missingQuestionText = true;
      return;
    }
    segments.push({ text: cleaned, language: language || null });
  };

  if (question.question_type === "speaking" || question.question_type === "spoken_answer" || question.question_type === "reading_aloud" || question.question_type === "sentence_repetition" || question.question_type === "pronunciation" || question.question_type === "spoken_fill_blank" || question.input_mode === "voice" || question.stt_enabled) {
    addSegment(question.instruction_text || question.prompt, learningLanguage);
    addSegment(question.target_text, learningLanguage);
    return { segments, missingQuestionText: missingQuestionText || !question.target_text?.trim() };
  }

  const questionText = question.tts_text || [question.passage, question.prompt].filter(Boolean).join(" ");
  addSegment(questionText, learningLanguage);
  if (!questionText?.trim()) {
    missingQuestionText = true;
  }

  const options = question.options || [];
  options.forEach((option) => {
    const optionText = typeof option === "string" ? option : option.text;
    if (!optionText?.trim()) {
      return;
    }
    addSegment(optionText, learningLanguage);
  });

  if (question.question_type === "sentence_rearrange" || question.question_type === "fill_in_the_blank" || question.input_mode === "letter_tiles" || question.input_mode === "word_tiles") {
    const sentence = question.tts_text || question.prompt;
    if (!sentence?.trim()) {
      missingQuestionText = true;
    }
  }

  return { segments, missingQuestionText };
}

export function buildAssessmentReadAllText(question: AssessmentQuestion) {
  return buildAssessmentReadAllSegments(question).segments
    .map((segment) => segment.text)
    .filter(Boolean)
    .join(" ");
}

export function buildSentenceCompletionSpeechText(question: AssessmentQuestion) {
  const baseLanguage = question.speech_language || question.learning_language || question.comfortable_language || "en";
  const prompt = question.tts_text || [question.passage, question.prompt].filter(Boolean).join(" ");
  return `${COMPLETE_SENTENCE_PROMPTS[(baseLanguage || "en").toLowerCase().split("-")[0] as SpeechLanguageCode] || COMPLETE_SENTENCE_PROMPTS.en} ${sanitizeSpeechText(prompt, baseLanguage, { blankStyle: "comma" })}`.trim();
}

export function buildSentenceRearrangeSpeechText(question: AssessmentQuestion) {
  const baseLanguage = question.speech_language || question.learning_language || question.comfortable_language || "en";
  const prompt = question.tts_text || [question.passage, question.prompt].filter(Boolean).join(" ");
  return `${REARRANGE_SENTENCE_PROMPTS[(baseLanguage || "en").toLowerCase().split("-")[0] as SpeechLanguageCode] || REARRANGE_SENTENCE_PROMPTS.en} ${sanitizeSpeechText(prompt, baseLanguage)}`.trim();
}
