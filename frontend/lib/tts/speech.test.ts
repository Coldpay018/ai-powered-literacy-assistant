import assert from "node:assert/strict";
import test from "node:test";

import type { AssessmentQuestion } from "../assessment/types";

import { LANGUAGE_OPTIONS, normalizeLanguage } from "../i18n/types";
import { translate } from "../i18n/translations";

import { buildAssessmentReadAllSegments } from "./content";
import { resolveSpeechLocale } from "./language";
import { pickSpeechVoice } from "./speech";

function voice(name: string, lang: string, isDefault = false) {
  return { name, lang, default: isDefault } as SpeechSynthesisVoice;
}

function assessmentQuestion(overrides: Partial<AssessmentQuestion>): AssessmentQuestion {
  return {
    attempt_question_id: 1,
    question_id: 1,
    section: "mcq",
    display_order: 1,
    question_type: "mcq",
    difficulty: "beginner",
    learning_language: "ta",
    prompt: "கேள்வி",
    options: [
      { id: "option_1", text: "ఎంపిక ఒకటి" },
      { id: "option_2", text: "ఎంపిక రెండు" },
    ],
    marks: 1,
    skill_tag: "vocabulary",
    ...overrides,
  };
}

test("Tamil and Telugu locales resolve to Indian speech locales", () => {
  assert.equal(resolveSpeechLocale("ta"), "ta-IN");
  assert.equal(resolveSpeechLocale("te"), "te-IN");
});

test("Kannada language options, translation, and speech locale resolve", () => {
  assert.equal(LANGUAGE_OPTIONS.some((option) => option.code === "kn" && option.label === "ಕನ್ನಡ"), true);
  assert.equal(normalizeLanguage("Kannada"), "kn");
  assert.equal(normalizeLanguage("kn-IN"), "kn");
  assert.equal(resolveSpeechLocale("kn"), "kn-IN");
  assert.equal(translate("kn", "assessment.start"), "ಮೌಲ್ಯಮಾಪನ ಪ್ರಾರಂಭಿಸಿ");
});

test("Kannada registration and profile UI strings resolve without English fallback", () => {
  const keys = [
    "common.platform",
    "common.switchToDark",
    "common.fullName",
    "common.educationLevel",
    "common.comfortableLanguage",
    "common.learningLanguage",
    "common.experienceLevel",
    "common.role",
    "auth.login",
    "auth.register",
    "auth.heroHeading",
    "auth.heroDescription",
    "auth.benefitLanguage",
    "auth.benefitPath",
    "auth.benefitProgress",
    "auth.registerJourney",
    "auth.quote",
    "auth.passwordPlaceholder",
    "auth.passwordCreatePlaceholder",
    "auth.loginButton",
    "auth.registerButton",
    "auth.creatingAccount",
    "auth.validationRequired",
    "option.education.primary",
    "option.role.learner",
    "profile.completeTitle",
    "profile.completeHelp",
    "profile.selectOption",
    "profile.saveChanges",
  ] as const;

  for (const key of keys) {
    assert.notEqual(translate("kn", key), translate("en", key), key);
  }
  assert.equal(translate("en", "auth.heroHeading"), "Learn. Practice. Grow.");
});

test("Kannada dashboard UI strings resolve without English fallback", () => {
  const keys = [
    "dashboard.primaryNav",
    "dashboard.mobilePrimaryNav",
    "dashboard.signedInAsUser",
    "dashboard.welcomeUser",
    "dashboard.activitiesThisWeek",
    "dashboard.learningStreakDays",
    "dashboard.levelLearner",
    "dashboard.progressChartAria",
    "dashboard.category.all",
    "dashboard.category.reading",
    "dashboard.category.writing",
    "dashboard.category.vocabulary",
    "dashboard.category.comprehension",
    "dashboard.resourceType.practice",
    "dashboard.resourceType.wordBank",
    "dashboard.resourceType.prompts",
    "dashboard.durationMinutes",
    "dashboard.timeSpentSeconds",
    "dashboard.lessonFallback",
    "dashboard.progressUnavailable",
    "learning.recommendedPath",
    "learning.loading",
    "learning.startLesson",
    "learning.continueLesson",
    "learning.reviewLesson",
    "gamification.streak.current",
    "gamification.streak.longest",
    "gamification.streak.completedToday",
    "gamification.streak.startToday",
    "gamification.streak.continueTomorrow",
    "gamification.streak.restarted",
    "gamification.streak.daySingular",
    "gamification.streak.dayPlural",
    "gamification.badges.title",
    "gamification.badges.progress",
    "gamification.badges.loading",
    "gamification.badges.loadError",
    "gamification.badges.empty",
    "gamification.badges.recent",
    "gamification.badges.nextLocked",
    "gamification.badges.requirement.initialAssessment",
    "gamification.badges.requirement.firstLesson",
    "gamification.badges.requirement.perfectQuiz",
    "gamification.badges.requirement.streakDays",
    "gamification.badges.requirement.totalXp",
    "gamification.badge.initialAssessment.name",
    "gamification.badge.firstLesson.name",
    "gamification.badge.perfectQuiz.name",
    "gamification.badge.streak3.description",
    "gamification.description.flashcardSessionCompleted",
    "flashcards.title",
    "flashcards.activityDescription",
    "flashcards.revealAnswer",
    "flashcards.needPractice",
    "flashcards.know",
    "flashcards.reviewComplete",
    "flashcards.cardsDue",
    "flashcards.cardsMastered",
    "flashcards.noDecksTitle",
    "flashcards.noDecksDescription",
    "flashcards.comeBackLater",
    "flashcards.xpEarned",
    "lesson.player",
    "lesson.loading",
    "lesson.questionsAttempted",
    "lesson.timeSpent",
    "tts.play",
    "tts.pause",
    "tts.resume",
    "tts.state.speaking",
  ] as const;

  for (const key of keys) {
    assert.notEqual(translate("kn", key), translate("en", key), key);
  }
  assert.equal(translate("kn", "dashboard.learningStreakDays", { count: 6 }).includes("6"), true);
  assert.equal(translate("kn", "gamification.streak.dayPlural", { count: 6 }).includes("6"), true);
  assert.equal(translate("kn", "dashboard.welcomeUser", { name: "Asha" }).includes("Asha"), true);
});

test("speech voice selection prefers exact, base language, then browser default", () => {
  assert.equal(pickSpeechVoice([voice("Tamil India", "ta-IN")], "ta")?.name, "Tamil India");
  assert.equal(pickSpeechVoice([voice("Tamil Base", "ta")], "ta-IN")?.name, "Tamil Base");
  assert.equal(pickSpeechVoice([voice("Default", "en-US", true)], "en")?.name, "Default");
  assert.equal(pickSpeechVoice([voice("Default", "en-US", true)], "te"), null);
  assert.equal(pickSpeechVoice([voice("Kannada Base", "kn")], "kn-IN")?.name, "Kannada Base");
  assert.equal(pickSpeechVoice([voice("Default", "en-US", true)], "kn"), null);
});

test("assessment speech uses displayed text without English option labels", () => {
  const segments = buildAssessmentReadAllSegments(assessmentQuestion({ learning_language: "te", prompt: "ప్రశ్న" })).segments;
  assert.deepEqual(
    segments.map((segment) => segment.language),
    ["te", "te", "te"],
  );
  assert.deepEqual(
    segments.map((segment) => segment.text),
    ["ప్రశ్న", "ఎంపిక ఒకటి", "ఎంపిక రెండు"],
  );
  assert.equal(segments.some((segment) => segment.text.startsWith("Option ")), false);
});
