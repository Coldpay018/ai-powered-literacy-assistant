from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from assessment_question_utils import (
    build_letter_tiles,
    build_word_tiles,
    normalize_sentence_text,
    ordered_words_match_sentence,
    word_tiles_match_sentence,
)
from adaptive_difficulty_service import evaluate_difficulty
from assessment_service import _dumps, _loads, _score_answer, _validate_answer, classify_proficiency, submit_attempt
from language_utils import normalize_language
from question_difficulty_service import build_starting_difficulty_profile, filter_question_query
from question_taxonomy import clamp_difficulty, derive_age_group, normalize_difficulty_value, normalize_question_skill, normalize_question_type
from seed_assessment import ASSESSMENT_VERSION


ASSESSMENT_SKILL_ORDER = ["reading", "writing", "vocabulary", "grammar", "comprehension"]
ASSESSMENT_SKILL_TARGETS = {
    "reading": 3,
    "writing": 3,
    "vocabulary": 3,
    "grammar": 2,
    "comprehension": 2,
}
MAX_TOTAL_QUESTIONS = sum(ASSESSMENT_SKILL_TARGETS.values())
QUESTION_TYPE_PREFERENCES = {
    "reading": ["reading_mcq", "mcq"],
    "writing": ["spoken_answer", "spoken_fill_blank", "reading_aloud", "sentence_repetition", "pronunciation", "sentence_rearrange", "copy_typing", "sentence_completion", "short_response"],
    "vocabulary": ["mcq", "reading_mcq"],
    "grammar": ["sentence_rearrange", "sentence_completion", "mcq", "short_response"],
    "comprehension": ["reading_mcq", "mcq"],
}

VOICE_QUESTION_TYPES = {
    "speaking",
    "spoken_answer",
    "reading_aloud",
    "sentence_repetition",
    "pronunciation",
    "spoken_fill_blank",
}

LANGUAGE_SCRIPT_RANGES = {
    "hi": ((0x0900, 0x097F),),
    "ta": ((0x0B80, 0x0BFF),),
    "te": ((0x0C00, 0x0C7F),),
    "kn": ((0x0C80, 0x0CFF),),
}

TRANSLATION_GLOSSARY: dict[tuple[str, str], dict[str, str]] = {
    ("en", "hi"): {
        "book": "किताब",
        "river": "नदी",
        "school": "स्कूल",
        "market": "बाज़ार",
        "garden": "बगीचा",
        "letter": "पत्र",
        "family": "परिवार",
        "morning": "सुबह",
        "Ravi": "रवि",
        "reads": "पढ़ता",
        "a": "एक",
        "child": "बच्चा",
        "keeps": "रखता",
        "pencil": "पेंसिल",
        "on": "पर",
        "table": "मेज",
        "Mina": "मीना",
        "waters": "पानी देती है",
        "small": "छोटा",
        "plant": "पौधा",
        "bus": "बस",
        "stops": "रुकती है",
        "near": "पास",
        "Asha": "आशा",
        "writes": "लिखती है",
        "friend": "सहेली",
        "teacher": "शिक्षक",
        "class": "कक्षा",
        "them": "उन्हें",
        "aloud": "ज़ोर से",
        "pages": "पन्ने",
        "every": "हर",
        "is": "है",
        "to": "को",
        "her": "उसकी",
        "his": "उसका",
        "younger": "छोटा",
        "brother": "भाई",
        "storybook": "कहानी की किताब",
        "board": "बोर्ड",
        "words": "शब्द",
        "desk": "मेज",
        "before": "से पहले",
        "studies": "पढ़ता है",
        "cleans": "साफ करता है",
        "sits": "बैठती है",
        "sings": "गाती है",
        "when": "जब",
        "sun": "सूरज",
        "rises": "उगता है",
        "small bird": "छोटी चिड़िया",
        "window": "खिड़की",
        "mother": "माँ",
        "rice": "चावल",
        "fresh vegetables": "ताज़ी सब्जियाँ",
    },
    ("hi", "en"): {
        "किताब": "book",
        "नदी": "river",
        "स्कूल": "school",
        "बाज़ार": "market",
        "बगीचा": "garden",
        "पत्र": "letter",
        "परिवार": "family",
        "सुबह": "morning",
        "रवि": "Ravi",
        "पढ़ता": "reads",
        "पढ़ना": "reading",
        "एक": "a",
        "बच्चा": "child",
        "रखता": "keeps",
        "पेंसिल": "pencil",
        "पर": "on",
        "मेज": "table",
        "मीना": "Mina",
        "पानी देती है": "waters",
        "छोटा": "small",
        "पौधा": "plant",
        "बस": "bus",
        "रुकती है": "stops",
        "पास": "near",
        "आशा": "Asha",
        "लिखती है": "writes",
        "सहेली": "friend",
        "शिक्षक": "teacher",
        "कक्षा": "class",
        "उन्हें": "them",
        "ज़ोर से": "aloud",
        "पन्ने": "pages",
        "हर": "every",
        "है": "is",
        "को": "to",
        "उसकी": "her",
        "उसका": "his",
        "छोटा भाई": "younger brother",
        "कहानी की किताब": "storybook",
        "बोर्ड": "board",
        "शब्द": "words",
        "से पहले": "before",
        "पढ़ता है": "studies",
        "साफ करता है": "cleans",
        "बैठती है": "sits",
        "गाती है": "sings",
        "जब": "when",
        "सूरज": "sun",
        "उगता है": "rises",
        "छोटी चिड़िया": "small bird",
        "खिड़की": "window",
        "माँ": "mother",
        "चावल": "rice",
        "ताज़ी सब्जियाँ": "fresh vegetables",
    },
    ("ta", "en"): {
        "ரவி": "Ravi",
        "ஒவ்வொரு": "every",
        "காலையும்": "morning",
        "புத்தகம்": "book",
        "வாசிக்கிறான்": "reads",
        "குழந்தை": "child",
        "பென்சிலை": "pencil",
        "மேசையில்": "on the table",
        "வைக்கிறது": "keeps",
        "மீனா": "Mina",
        "சிறிய": "small",
        "செடிக்கு": "to the plant",
        "தண்ணீர்": "water",
        "ஊற்றுகிறாள்": "waters",
        "பேருந்து": "bus",
        "பள்ளி": "school",
        "அருகில்": "near",
        "நிற்கிறது": "stops",
    },
    ("te", "en"): {
        "రవి": "Ravi",
        "ప్రతి": "every",
        "ఉదయం": "morning",
        "పుస్తకం": "book",
        "చదువుతాడు": "reads",
        "బిడ్డ": "child",
        "పెన్సిల్‌ను": "pencil",
        "బల్లపై": "on the table",
        "పెడుతుంది": "keeps",
        "మీనా": "Mina",
        "చిన్న": "small",
        "మొక్కకు": "to the plant",
        "నీరు": "water",
        "పోస్తుంది": "waters",
        "బస్సు": "bus",
        "పాఠశాల": "school",
        "దగ్గర": "near",
        "ఆగుతుంది": "stops",
    },
}


def _translation_lookup(source_language: str, target_language: str, text: str | None) -> str | None:
    if not text:
        return None
    source = source_language.lower().split("-")[0]
    target = target_language.lower().split("-")[0]
    if source == target:
        return None
    glossary = TRANSLATION_GLOSSARY.get((source, target), {})
    normalized = unicodedata.normalize("NFC", text).strip().strip(".,!?;:。！？।")
    if not normalized:
        return None
    return glossary.get(normalized) or glossary.get(normalized.casefold())


def _pair_option_payloads(
    question: models.AssessmentQuestion,
    translation_question: models.AssessmentQuestion | None,
    translation_language: str | None,
) -> list[dict[str, Any]] | None:
    if not question.options_json:
        return None

    source_options = _loads(question.options_json, [])
    if not isinstance(source_options, list):
        return None

    translated_options = None
    if translation_question and translation_question.options_json:
        translated_options = _loads(translation_question.options_json, [])

    paired: list[dict[str, Any]] = []
    for index, option in enumerate(source_options):
        if not isinstance(option, dict) or not isinstance(option.get("id"), str):
            continue
        translation = None
        if isinstance(translated_options, list) and index < len(translated_options):
            translated_option = translated_options[index]
            if isinstance(translated_option, dict) and isinstance(translated_option.get("text"), str):
                translation = translated_option["text"]
        if translation is None and translation_language:
            translation = _translation_lookup(question.learning_language, translation_language, option.get("text"))
        paired.append({**option, "translation": translation})
    return paired


def _pair_tile_payloads(
    question: models.AssessmentQuestion,
    tiles: list[dict[str, Any]] | None,
    translation_question: models.AssessmentQuestion | None,
    translation_language: str | None,
) -> list[dict[str, Any]] | None:
    if not tiles:
        return None

    if question.question_type == "sentence_completion":
        return [
            {
                **tile,
                "translation": _translation_lookup(question.learning_language, translation_language or question.learning_language, tile.get("value")),
            }
            for tile in tiles
            if isinstance(tile, dict) and isinstance(tile.get("id"), str)
        ]

    translated_tokens: list[str] = []
    if translation_question:
        translation_reference, _, _ = _canonical_word_tile_answer(translation_question)
        translated_tokens = _sentence_tokens(translation_reference)

    paired_tiles: list[dict[str, Any]] = []
    for tile in tiles:
        if not isinstance(tile, dict) or not isinstance(tile.get("id"), str):
            continue
        original_order = tile.get("original_order")
        translation = _translation_lookup(question.learning_language, translation_language or question.learning_language, tile.get("value"))
        if isinstance(original_order, int) and 0 <= original_order < len(translated_tokens):
            translation = translation or translated_tokens[original_order]
        paired_tiles.append({**tile, "translation": translation})
    return paired_tiles


def _loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _answer_hash(attempt_question_id: int, answer: dict[str, Any]) -> str:
    payload = json.dumps(
        {"attempt_question_id": attempt_question_id, "answer": answer},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sanitize_spoken_text(text: str) -> str:
    normalized = normalize_sentence_text(text, case_sensitive=True, allow_terminal_punctuation=False)
    normalized = normalized.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
    normalized = normalized.replace(" :", ":").replace(" ;", ";")
    return normalized.strip()


def _language_characters_match(language: str, text: str) -> bool:
    if not text.strip():
        return False

    if language == "en":
        for character in text:
            code = ord(character)
            for ranges in LANGUAGE_SCRIPT_RANGES.values():
                if any(start <= code <= end for start, end in ranges):
                    return False
        return True

    expected_ranges = LANGUAGE_SCRIPT_RANGES.get(language)
    if not expected_ranges:
        return True

    has_expected_script = False
    for character in text:
        code = ord(character)
        if any(start <= code <= end for start, end in expected_ranges):
            has_expected_script = True
        for script, ranges in LANGUAGE_SCRIPT_RANGES.items():
            if script == language:
                continue
            if any(start <= code <= end for start, end in ranges):
                return False
    return has_expected_script


def _question_language_payload_text(question: models.AssessmentQuestion) -> list[str]:
    payload: list[str] = []
    for value in (question.prompt, question.passage):
        if isinstance(value, str) and value.strip():
            payload.append(value)

    options = _loads(question.options_json, [])
    if isinstance(options, list):
        for option in options:
            if isinstance(option, dict):
                option_text = option.get("text")
                if isinstance(option_text, str) and option_text.strip():
                    payload.append(option_text)

    correct = _loads(question.correct_answer_json, {})
    if isinstance(correct, dict):
        for key in ("display_text", "reference_text"):
            value = correct.get(key)
            if isinstance(value, str) and value.strip():
                payload.append(value)
        for key in ("accepted_answers", "required_keywords"):
            values = correct.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip():
                        payload.append(value)
    return payload


def _question_language_matches(question: models.AssessmentQuestion, language: str) -> bool:
    try:
        normalized_question_language = normalize_language(question.language)
    except ValueError:
        return False

    if normalized_question_language != language:
        return False

    try:
        normalized_learning_language = normalize_language(question.learning_language)
    except ValueError:
        return False

    if normalized_learning_language != language:
        return False

    payload_text = _question_language_payload_text(question)
    if not payload_text:
        return False

    has_expected_script = False
    for text in payload_text:
        if not _language_characters_match(language, text):
            return False
        if language != "en":
            ranges = LANGUAGE_SCRIPT_RANGES.get(language, ())
            if any(any(start <= ord(character) <= end for start, end in ranges) for character in text):
                has_expected_script = True

    return True if language == "en" else has_expected_script


def _question_tile_mode(question: models.AssessmentQuestion) -> str | None:
    if question.question_type == "sentence_completion":
        return "letter_tiles"
    if question.question_type == "sentence_rearrange":
        return "word_tiles"
    return None


def _question_input_mode(question: models.AssessmentQuestion) -> str | None:
    if question.question_type in VOICE_QUESTION_TYPES:
        return "voice"
    return _question_tile_mode(question)


def _stable_suffix(stable_key: str) -> str:
    return stable_key.split("-", 1)[1] if "-" in stable_key else stable_key


def _translation_question(
    db: Session,
    question: models.AssessmentQuestion,
    target_language: str | None,
) -> models.AssessmentQuestion | None:
    if not target_language:
        return None

    try:
        normalized_target = normalize_language(target_language)
    except ValueError:
        return None

    try:
        source_language = normalize_language(question.language)
    except ValueError:
        source_language = question.language

    if normalized_target == source_language:
        return question

    target_stable_key = f"{normalized_target}-{_stable_suffix(question.stable_key)}"
    return (
        db.query(models.AssessmentQuestion)
        .filter(
            models.AssessmentQuestion.assessment_version == question.assessment_version,
            models.AssessmentQuestion.stable_key == target_stable_key,
            models.AssessmentQuestion.is_active == True,
        )
        .first()
    )


def _sentence_tokens(value: str | None) -> list[str]:
    normalized = unicodedata.normalize("NFC", value or "").replace("\r\n", " ").replace("\r", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.split(" ") if normalized else []


def _canonical_letter_tile_answer(question: models.AssessmentQuestion) -> str | None:
    correct = _loads(question.correct_answer_json, {})
    candidate = ""
    accepted = correct.get("accepted_answers")
    if isinstance(accepted, list):
        candidate = next(
            (
                str(item).strip()
                for item in accepted
                if isinstance(item, str)
                and item.strip()
                and not any(char.isspace() for char in str(item).strip())
            ),
            "",
        )
    if not candidate:
        reference = correct.get("reference_text")
        if isinstance(reference, str):
            candidate = reference.strip()
    if not candidate:
        return None

    normalized = normalize_sentence_text(candidate, case_sensitive=True, allow_terminal_punctuation=True)
    if not normalized or any(char.isspace() for char in normalized):
        return None
    return normalized


def _canonical_word_tile_answer(question: models.AssessmentQuestion) -> tuple[str | None, bool, bool]:
    correct = _loads(question.correct_answer_json, {})
    reference = correct.get("reference_text")
    if not isinstance(reference, str) or not reference.strip():
        return None, False, True
    case_sensitive = bool(correct.get("case_sensitive", False))
    allow_terminal_punctuation = bool(correct.get("allow_terminal_punctuation", True))
    return reference.strip(), case_sensitive, allow_terminal_punctuation


def _ordered_word_tiles_from_question(question: models.AssessmentQuestion) -> list[dict[str, Any]] | None:
    correct = _loads(question.correct_answer_json, {})
    reference = correct.get("reference_text") if isinstance(correct, dict) else None
    ordered_words = correct.get("ordered_words") if isinstance(correct, dict) else None
    if isinstance(ordered_words, list) and ordered_words_match_sentence(ordered_words, reference):
        valid_words = [
            word
            for word in ordered_words
            if isinstance(word, dict)
            and isinstance(word.get("value"), str)
            and isinstance(word.get("original_order"), int)
        ]
        return [
            {
                "id": f"tile_{index + 1}",
                "value": word["value"],
                "translation": word.get("translation"),
                "original_order": int(word["original_order"]),
            }
            for index, word in enumerate(sorted(valid_words, key=lambda item: item["original_order"]))
        ]
    if isinstance(reference, str) and reference.strip():
        return sorted(build_word_tiles(reference), key=lambda tile: tile["original_order"])
    return None


def _word_tiles_have_order(tiles: list[dict[str, Any]] | None) -> bool:
    return bool(
        tiles
        and all(
            isinstance(tile, dict)
            and isinstance(tile.get("id"), str)
            and isinstance(tile.get("value"), str)
            and isinstance(tile.get("original_order"), int)
            for tile in tiles
        )
    )


def _valid_word_tiles_for_answer(tiles: list[dict[str, Any]] | None, answer_text: str | None) -> bool:
    return _word_tiles_have_order(tiles) and word_tiles_match_sentence(tiles, answer_text)


def _shuffled_word_tiles_from_question(question: models.AssessmentQuestion) -> list[dict[str, Any]] | None:
    canonical_answer = _canonical_word_tile_answer(question)[0]
    ordered_tiles = _ordered_word_tiles_from_question(question)
    if not canonical_answer or not ordered_tiles:
        return None
    if not _valid_word_tiles_for_answer(ordered_tiles, canonical_answer):
        return None
    shuffled_tiles = [dict(tile) for tile in ordered_tiles]
    random.SystemRandom().shuffle(shuffled_tiles)
    return shuffled_tiles


def _is_practice_only_question(question: models.AssessmentQuestion) -> bool:
    scoring = _loads(question.scoring_config_json, {})
    return bool(isinstance(scoring, dict) and scoring.get("practice_only"))


def _is_valid_assessment_question(question: models.AssessmentQuestion) -> bool:
    try:
        normalized_language = normalize_language(question.language)
    except ValueError:
        return False

    if not _question_language_matches(question, normalized_language):
        return False

    try:
        question_type = normalize_question_type(question.question_type)
    except ValueError:
        return False

    if question_type in {"multiple_choice", "reading_comprehension"}:
        options = _loads(question.options_json, [])
        if not isinstance(options, list) or len(options) < 2:
            return False
        valid_options = [
            option
            for option in options
            if isinstance(option, dict)
            and isinstance(option.get("id"), str)
            and isinstance(option.get("text"), str)
            and option["text"].strip()
        ]
        if len(valid_options) != len(options):
            return False
        correct = _loads(question.correct_answer_json, {})
        correct_option_id = correct.get("correct_option_id")
        if not isinstance(correct_option_id, str):
            return False
        correct_matches = [option for option in valid_options if option["id"] == correct_option_id]
        if len(correct_matches) != 1:
            return False
        return True

    if question_type == "fill_in_the_blank":
        return bool(_canonical_letter_tile_answer(question))

    if question_type == "sentence_ordering":
        canonical_answer = _canonical_word_tile_answer(question)[0]
        ordered_tiles = _ordered_word_tiles_from_question(question)
        return bool(canonical_answer) and _valid_word_tiles_for_answer(ordered_tiles, canonical_answer)

    if question_type in VOICE_QUESTION_TYPES:
        if _is_practice_only_question(question):
            return False
        correct = _loads(question.correct_answer_json, {})
        if not isinstance(correct, dict):
            return False
        display_text = correct.get("display_text")
        reference_text = correct.get("reference_text")
        accepted_answers = correct.get("accepted_answers")
        target_text = None
        if isinstance(display_text, str) and display_text.strip():
            target_text = display_text.strip()
        elif isinstance(reference_text, str) and reference_text.strip():
            target_text = reference_text.strip()
        elif isinstance(accepted_answers, list):
            target_text = next((str(item).strip() for item in accepted_answers if isinstance(item, str) and str(item).strip()), None)
        if not target_text:
            return False
        if question_type == "spoken_fill_blank":
            if "____" not in target_text:
                return False
            if not isinstance(accepted_answers, list):
                return False
            valid_answers = [str(item).strip() for item in accepted_answers if isinstance(item, str) and str(item).strip()]
            if len(valid_answers) != 1:
                return False
            if not isinstance(reference_text, str) or not reference_text.strip():
                return False
            return True
        if question_type in {"spoken_answer", "speaking"}:
            return isinstance(accepted_answers, list) and any(isinstance(item, str) and item.strip() for item in accepted_answers)
        return isinstance(reference_text, str) and bool(reference_text.strip())

    return True


def _canonical_tile_answer(question: models.AssessmentQuestion) -> str | None:
    correct = _loads(question.correct_answer_json, {})
    candidate = ""
    accepted = correct.get("accepted_answers")
    if isinstance(accepted, list):
        candidate = next(
            (
                str(item).strip()
                for item in accepted
                if isinstance(item, str)
                and item.strip()
                and not any(char.isspace() for char in str(item).strip())
            ),
            "",
        )
    if not candidate:
        reference = correct.get("reference_text")
        if isinstance(reference, str):
            candidate = reference.strip()
    if not candidate:
        return None

    normalized = unicodedata.normalize("NFC", candidate).strip().strip(".,!?;:।॥'\"")
    if not normalized or any(char.isspace() for char in normalized):
        return None
    return normalized


def _build_shuffled_tiles(answer_text: str) -> list[dict[str, str]]:
    characters = [character for character in unicodedata.normalize("NFC", answer_text) if character.strip()]
    if not characters:
        return []
    tiles = [{"id": f"tile_{index + 1}", "value": character} for index, character in enumerate(characters)]
    random.SystemRandom().shuffle(tiles)
    return tiles


def _question_speech_text(question: models.AssessmentQuestion) -> str:
    parts = [part.strip() for part in (question.passage, question.prompt) if isinstance(part, str) and part.strip()]
    return _sanitize_spoken_text(" ".join(parts))


def _voice_question_fields(
    question: models.AssessmentQuestion,
    translation_question: models.AssessmentQuestion | None,
    translation_language: str | None,
) -> dict[str, Any]:
    correct = _loads(question.correct_answer_json, {})
    translated_correct = _loads(translation_question.correct_answer_json, {}) if translation_question else {}

    target_text: str | None = None
    target_translation: str | None = None

    display_text = correct.get("display_text")
    if isinstance(display_text, str) and display_text.strip():
        target_text = display_text.strip()
    else:
        reference_text = correct.get("reference_text")
        if isinstance(reference_text, str) and reference_text.strip():
            target_text = reference_text.strip()
        else:
            accepted_answers = correct.get("accepted_answers")
            if isinstance(accepted_answers, list):
                target_text = next(
                    (
                        str(item).strip()
                        for item in accepted_answers
                        if isinstance(item, str) and str(item).strip()
                    ),
                    None,
                )

    translated_display = translated_correct.get("display_text")
    if isinstance(translated_display, str) and translated_display.strip():
        target_translation = translated_display.strip()
    else:
        translated_reference = translated_correct.get("reference_text")
        if isinstance(translated_reference, str) and translated_reference.strip():
            target_translation = translated_reference.strip()
        elif translation_language:
            target_translation = _translation_lookup(question.learning_language, translation_language, target_text)

    return {
        "instruction_text": question.prompt,
        "target_text": target_text,
        "target_translation": target_translation,
        "tts_text": target_text or _question_speech_text(question),
    }


def _ensure_attempt_question_tiles(
    db: Session,
    attempt_question: models.AssessmentAttemptQuestion,
    question: models.AssessmentQuestion,
) -> None:
    tile_mode = _question_tile_mode(question)
    existing_tiles = _loads(attempt_question.shuffled_tiles_json, None)
    if tile_mode == "letter_tiles":
        if existing_tiles:
            return
        canonical_answer = _canonical_letter_tile_answer(question)
        if not canonical_answer:
            return
        attempt_question.shuffled_tiles_json = _dumps(build_letter_tiles(canonical_answer))
    elif tile_mode == "word_tiles":
        canonical_answer, _, _ = _canonical_word_tile_answer(question)
        if not canonical_answer:
            return
        if _valid_word_tiles_for_answer(existing_tiles, canonical_answer):
            return
        shuffled_tiles = _shuffled_word_tiles_from_question(question)
        if not shuffled_tiles:
            return
        attempt_question.shuffled_tiles_json = _dumps(shuffled_tiles)
    else:
        return
    db.add(attempt_question)
    db.flush()
    db.commit()


def _current_attempt_question(
    db: Session,
    attempt_id: int,
) -> tuple[models.AssessmentAttemptQuestion, models.AssessmentQuestion] | None:
    rows = (
        db.query(models.AssessmentAttemptQuestion, models.AssessmentQuestion)
        .join(models.AssessmentQuestion, models.AssessmentAttemptQuestion.question_id == models.AssessmentQuestion.id)
        .outerjoin(
            models.AssessmentAnswer,
            models.AssessmentAnswer.attempt_question_id == models.AssessmentAttemptQuestion.id,
        )
        .filter(models.AssessmentAttemptQuestion.attempt_id == attempt_id, models.AssessmentAnswer.id.is_(None))
        .order_by(models.AssessmentAttemptQuestion.display_order.desc())
        .all()
    )
    return rows[0] if rows else None


def _attempt_questions(db: Session, attempt_id: int):
    return (
        db.query(models.AssessmentAttemptQuestion, models.AssessmentQuestion, models.AssessmentAnswer)
        .join(models.AssessmentQuestion, models.AssessmentAttemptQuestion.question_id == models.AssessmentQuestion.id)
        .outerjoin(
            models.AssessmentAnswer,
            models.AssessmentAnswer.attempt_question_id == models.AssessmentAttemptQuestion.id,
        )
        .filter(models.AssessmentAttemptQuestion.attempt_id == attempt_id)
        .order_by(models.AssessmentAttemptQuestion.display_order)
        .all()
    )


def _attempt_answers(db: Session, attempt_id: int) -> dict[int, models.AssessmentAnswer]:
    rows = (
        db.query(models.AssessmentAnswer)
        .filter(models.AssessmentAnswer.attempt_id == attempt_id)
        .all()
    )
    return {row.attempt_question_id: row for row in rows}


def _skill_progress(db: Session, attempt_id: int) -> dict[str, dict[str, int]]:
    progress = {
        skill: {"answered": 0, "correct": 0, "incorrect": 0}
        for skill in ASSESSMENT_SKILL_ORDER
    }
    for attempt_question, question, answer in _attempt_questions(db, attempt_id):
        skill = normalize_question_skill(question.skill or question.skill_tag)
        if skill not in progress or answer is None:
            continue
        progress[skill]["answered"] += 1
        if answer.is_correct is True:
            progress[skill]["correct"] += 1
        elif answer.is_correct is False:
            progress[skill]["incorrect"] += 1
    return progress


def _skill_difficulty_snapshot(db: Session, user: models.User) -> dict[str, int]:
    profile = build_starting_difficulty_profile(db, user)
    return {skill: int(value) for skill, value in profile["skill_difficulties"].items()}


def _completed_skills(db: Session, user: models.User, attempt_id: int) -> list[str]:
    progress = _skill_progress(db, attempt_id)
    remaining = _skill_difficulty_snapshot(db, user)
    completed = []
    for skill in ASSESSMENT_SKILL_ORDER:
        if progress[skill]["answered"] >= ASSESSMENT_SKILL_TARGETS[skill]:
            completed.append(skill)
            continue
        if not _candidate_questions(db, user, attempt_id, skill, remaining[skill]):
            completed.append(skill)
    return completed


def _question_payload(
    attempt_question: models.AssessmentAttemptQuestion,
    question: models.AssessmentQuestion,
    db: Session,
    translation_language: str | None = None,
) -> dict[str, Any]:
    try:
        difficulty_rating = normalize_difficulty_value(question.difficulty_rating)
    except ValueError:
        difficulty_rating = None
    try:
        skill = normalize_question_skill(question.skill or question.skill_tag)
    except ValueError:
        skill = None
    options = _loads(attempt_question.shuffled_options_json, None)
    tiles = _loads(attempt_question.shuffled_tiles_json, None)
    translation_question = _translation_question(db, question, translation_language)
    translated_options = options
    translated_tiles = tiles
    if options and any(isinstance(option, dict) and option.get("translation") is None for option in options):
        translated_options = _pair_option_payloads(question, translation_question, translation_language) or options
    if tiles and (
        question.question_type == "sentence_rearrange"
        or any(isinstance(tile, dict) and tile.get("translation") is None for tile in tiles)
    ):
        translated_tiles = _pair_tile_payloads(question, tiles, translation_question, translation_language) or tiles
    passage_translation = translation_question.passage if translation_question and translation_question.passage else None
    prompt_translation = translation_question.prompt if translation_question else None
    voice_fields = _voice_question_fields(question, translation_question, translation_language)
    return {
        "question_id": question.id,
        "attempt_question_id": attempt_question.id,
        "section": attempt_question.section,
        "display_order": attempt_question.display_order,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "difficulty_rating": difficulty_rating,
        "skill": skill,
        "age_group": question.age_group,
        "experience_level": question.experience_level,
        "comfortable_language": question.comfortable_language,
        "learning_language": question.learning_language,
        "instruction_text": voice_fields["instruction_text"] if question.question_type in VOICE_QUESTION_TYPES else None,
        "target_text": voice_fields["target_text"] if question.question_type in VOICE_QUESTION_TYPES else None,
        "target_translation": voice_fields["target_translation"] if question.question_type in VOICE_QUESTION_TYPES else None,
        "tts_text": voice_fields["tts_text"] if question.question_type in VOICE_QUESTION_TYPES else _question_speech_text(question),
        "tts_read_options": [
            option.get("text", "")
            for option in options
            if isinstance(option, dict)
        ] if isinstance(options, list) else None,
        "input_mode": _question_input_mode(question) if (tiles or question.question_type in VOICE_QUESTION_TYPES) else None,
        "shuffled_tiles": translated_tiles,
        "speech_language": question.learning_language or question.comfortable_language,
        "stt_enabled": question.question_type in VOICE_QUESTION_TYPES,
        "translation_language": translation_language or None,
        "passage": question.passage,
        "passage_translation": passage_translation,
        "prompt": question.prompt,
        "prompt_translation": prompt_translation,
        "options": translated_options,
        "marks": attempt_question.maximum_marks,
        "skill_tag": question.skill_tag,
    }


def _serialize_attempt(
    db: Session,
    attempt: models.AssessmentAttempt,
) -> dict[str, Any]:
    current = _current_attempt_question(db, attempt.id)
    answered_questions = (
        db.query(models.AssessmentAnswer)
        .filter(models.AssessmentAnswer.attempt_id == attempt.id)
        .count()
    )
    user = (
        db.query(models.User)
        .filter(models.User.id == attempt.user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    profile = build_starting_difficulty_profile(db, user, None)["skill_difficulties"]
    current_question = None
    if current:
        _ensure_attempt_question_tiles(db, current[0], current[1])
        current_question = _question_payload(*current, db=db, translation_language=user.comfortable_language)
        profile[current_question["skill"]] = int(
            db.query(models.LearnerSkillDifficulty.current_difficulty)
            .filter(
                models.LearnerSkillDifficulty.user_id == attempt.user_id,
                models.LearnerSkillDifficulty.skill == current_question["skill"],
            )
            .scalar()
            or profile[current_question["skill"]]
        )

    progress = _skill_progress(db, attempt.id)
    completed_skills = [skill for skill in ASSESSMENT_SKILL_ORDER if progress[skill]["answered"] >= ASSESSMENT_SKILL_TARGETS[skill]]
    return {
        "attempt_id": attempt.id,
        "assessment_title": "Initial Literacy Assessment",
        "assessment_version": attempt.assessment_version,
        "language": attempt.preferred_language,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "answered_questions": answered_questions,
        "total_questions": MAX_TOTAL_QUESTIONS,
        "completed_skills": completed_skills,
        "current_question": current_question,
        "assessment_complete": attempt.status == "evaluated",
        "final_skill_profile": profile,
    }


def _candidate_questions(
    db: Session,
    user: models.User,
    attempt_id: int,
    skill: str,
    difficulty: int,
) -> list[models.AssessmentQuestion]:
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt_id)
        .first()
    )
    if attempt is None:
        return []
    age_group = derive_age_group(user.age)
    answers = _attempt_answers(db, attempt_id)
    excluded_ids = [answer.question_id for answer in answers.values()]
    candidates: list[models.AssessmentQuestion] = []
    ordered_difficulties = sorted(
        range(1, 6),
        key=lambda value: (abs(value - difficulty), value),
    )
    for current_difficulty in ordered_difficulties:
        query = db.query(models.AssessmentQuestion)
        query = filter_question_query(
            query,
            models.AssessmentQuestion,
            skill=skill,
            difficulty=current_difficulty,
            learning_language=user.learning_language,
        )
        query = query.filter(models.AssessmentQuestion.assessment_version == attempt.assessment_version)
        query = query.filter(models.AssessmentQuestion.is_active == True)
        if excluded_ids:
            query = query.filter(~models.AssessmentQuestion.id.in_(excluded_ids))
        candidates = [question for question in query.all() if _is_valid_assessment_question(question)]
        if candidates:
            break
    preferred_types = QUESTION_TYPE_PREFERENCES.get(skill, [])
    return sorted(
        candidates,
        key=lambda question: (
            0 if question.age_group == age_group else 1,
            0 if question.experience_level == user.experience_level else 1,
            0 if question.comfortable_language == user.comfortable_language else 1,
            preferred_types.index(question.question_type) if question.question_type in preferred_types else len(preferred_types),
            question.stable_key,
        ),
    )


def _select_question_for_skill(
    db: Session,
    user: models.User,
    attempt_id: int,
    skill: str,
    difficulty: int,
) -> models.AssessmentQuestion | None:
    candidates = _candidate_questions(db, user, attempt_id, skill, difficulty)
    return candidates[0] if candidates else None


def _next_skill_to_assess(db: Session, user: models.User, attempt_id: int) -> str | None:
    progress = _skill_progress(db, attempt_id)
    snapshot = _skill_difficulty_snapshot(db, user)
    for skill in ASSESSMENT_SKILL_ORDER:
        if progress[skill]["answered"] >= ASSESSMENT_SKILL_TARGETS[skill]:
            continue
        if _candidate_questions(db, user, attempt_id, skill, snapshot[skill]):
            return skill
    return None


def _create_attempt_question(
    db: Session,
    attempt: models.AssessmentAttempt,
    question: models.AssessmentQuestion,
    translation_language: str | None = None,
) -> models.AssessmentAttemptQuestion:
    last_display = (
        db.query(models.AssessmentAttemptQuestion.display_order)
        .filter(models.AssessmentAttemptQuestion.attempt_id == attempt.id)
        .order_by(models.AssessmentAttemptQuestion.display_order.desc())
        .first()
    )
    display_order = (last_display[0] if last_display else 0) + 1
    shuffled_options = None
    if question.options_json:
        translation_question = _translation_question(db, question, translation_language)
        shuffled_options = _pair_option_payloads(question, translation_question, translation_language)
        if shuffled_options is not None:
            random.SystemRandom().shuffle(shuffled_options)
    shuffled_tiles = None
    tile_mode = _question_tile_mode(question)
    if tile_mode == "letter_tiles":
        canonical_answer = _canonical_letter_tile_answer(question)
        if canonical_answer:
            shuffled_tiles = build_letter_tiles(canonical_answer)
    elif tile_mode == "word_tiles":
        shuffled_tiles = _shuffled_word_tiles_from_question(question)
    if shuffled_tiles is not None:
        translation_question = _translation_question(db, question, translation_language)
        shuffled_tiles = _pair_tile_payloads(question, shuffled_tiles, translation_question, translation_language)
    attempt_question = models.AssessmentAttemptQuestion(
        attempt_id=attempt.id,
        question_id=question.id,
        section=question.section,
        display_order=display_order,
        shuffled_options_json=_dumps(shuffled_options) if shuffled_options is not None else None,
        shuffled_tiles_json=_dumps(shuffled_tiles) if shuffled_tiles is not None else None,
        maximum_marks=question.marks,
    )
    db.add(attempt_question)
    db.flush()
    return attempt_question


def _ensure_active_question(db: Session, attempt: models.AssessmentAttempt) -> dict[str, Any]:
    current = _current_attempt_question(db, attempt.id)
    if current:
        return _serialize_attempt(db, attempt)

    if attempt.status != "in_progress":
        return _serialize_attempt(db, attempt)

    user = (
        db.query(models.User)
        .filter(models.User.id == attempt.user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    skill = _next_skill_to_assess(db, user, attempt.id)
    if skill is None:
        return complete_assessment(db, user, attempt.id)

    difficulty_map = _skill_difficulty_snapshot(db, user)
    candidates = _candidate_questions(db, user, attempt.id, skill, difficulty_map[skill])
    if not candidates:
        return complete_assessment(db, user, attempt.id)

    _create_attempt_question(db, attempt, candidates[0], translation_language=user.comfortable_language)
    db.commit()
    db.refresh(attempt)
    return _serialize_attempt(db, attempt)


def get_initial_assessment(db: Session):
    assessment = (
        db.query(models.Assessment)
        .filter(models.Assessment.version == ASSESSMENT_VERSION, models.Assessment.is_active == True)
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def get_status(db: Session, user: models.User):
    if user.role != "learner":
        return {
            "required": False,
            "completed": False,
            "has_in_progress_attempt": False,
            "attempt_id": None,
            "proficiency_level": None,
            "reason": "role_not_learner",
        }

    result = (
        db.query(models.AssessmentResult)
        .filter(
            models.AssessmentResult.user_id == user.id,
            models.AssessmentResult.assessment_version == ASSESSMENT_VERSION,
        )
        .first()
    )
    if result:
        return {
            "required": False,
            "completed": True,
            "has_in_progress_attempt": False,
            "attempt_id": result.attempt_id,
            "proficiency_level": result.proficiency_level,
            "reason": None,
        }

    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    return {
        "required": True,
        "completed": False,
        "has_in_progress_attempt": attempt is not None,
        "attempt_id": attempt.id if attempt else None,
        "proficiency_level": None,
        "reason": None,
    }


def start_or_resume(db: Session, user: models.User):
    if user.role != "learner":
        raise HTTPException(status_code=403, detail="Assessment is required only for learners")

    completed = (
        db.query(models.AssessmentResult)
        .filter(
            models.AssessmentResult.user_id == user.id,
            models.AssessmentResult.assessment_version == ASSESSMENT_VERSION,
        )
        .first()
    )
    if completed:
        raise HTTPException(status_code=409, detail="Assessment already completed")

    existing = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    if existing:
        return _ensure_active_question(db, existing)

    assessment = get_initial_assessment(db)
    try:
        language = normalize_language(user.learning_language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported learning language") from exc
    attempt = models.AssessmentAttempt(
        user_id=user.id,
        assessment_id=assessment.id,
        assessment_version=assessment.version,
        preferred_language=language,
        status="in_progress",
    )
    db.add(attempt)
    db.flush()

    snapshot = _skill_difficulty_snapshot(db, user)
    first_skill = None
    for skill in ASSESSMENT_SKILL_ORDER:
        if _candidate_questions(db, user, attempt.id, skill, snapshot[skill]):
            first_skill = skill
            break
    if first_skill is None:
        db.rollback()
        raise HTTPException(status_code=422, detail="No suitable assessment questions available")

    first_question = _candidate_questions(db, user, attempt.id, first_skill, snapshot[first_skill])[0]
    _create_attempt_question(db, attempt, first_question, translation_language=user.comfortable_language)
    db.commit()
    db.refresh(attempt)
    return _serialize_attempt(db, attempt)


def current_attempt(db: Session, user: models.User):
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(
            models.AssessmentAttempt.user_id == user.id,
            models.AssessmentAttempt.assessment_version == ASSESSMENT_VERSION,
            models.AssessmentAttempt.status == "in_progress",
        )
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return _ensure_active_question(db, attempt)


def _current_answer_row(db: Session, attempt_question_id: int, attempt_id: int) -> models.AssessmentAnswer | None:
    return (
        db.query(models.AssessmentAnswer)
        .filter(
            models.AssessmentAnswer.attempt_id == attempt_id,
            models.AssessmentAnswer.attempt_question_id == attempt_question_id,
        )
        .first()
    )


def submit_assessment_answer(
    db: Session,
    user: models.User,
    attempt_id: int,
    attempt_question_id: int,
    answer: dict[str, Any],
):
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt_id, models.AssessmentAttempt.user_id == user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="Attempt already submitted")

    attempt_question = (
        db.query(models.AssessmentAttemptQuestion)
        .join(models.AssessmentQuestion, models.AssessmentAttemptQuestion.question_id == models.AssessmentQuestion.id)
        .filter(
            models.AssessmentAttemptQuestion.id == attempt_question_id,
            models.AssessmentAttemptQuestion.attempt_id == attempt.id,
        )
        .first()
    )
    if not attempt_question:
        raise HTTPException(status_code=404, detail="Attempt question not found")

    current_active = _current_attempt_question(db, attempt.id)
    if current_active and current_active[0].id != attempt_question_id:
        existing_answer = _current_answer_row(db, attempt_question_id, attempt.id)
        if existing_answer is None:
            raise HTTPException(status_code=409, detail="Question is not currently active")

    question = (
        db.query(models.AssessmentQuestion)
        .filter(models.AssessmentQuestion.id == attempt_question.question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    normalized_hash = _answer_hash(attempt_question_id, answer)
    existing_answer = _current_answer_row(db, attempt_question_id, attempt.id)
    if existing_answer:
        if existing_answer.submission_hash == normalized_hash:
            return {
                "correct": bool(existing_answer.is_correct),
                "skill": normalize_question_skill(question.skill or question.skill_tag),
                "question_id": question.id,
                "attempt_question_id": attempt_question.id,
                "difficulty": {
                    "skill": normalize_question_skill(question.skill or question.skill_tag),
                    "previous_difficulty": normalize_difficulty_value(question.difficulty_rating) or 1,
                    "new_difficulty": normalize_difficulty_value(question.difficulty_rating) or 1,
                    "correct_streak": 0,
                    "incorrect_streak": 0,
                    "rolling_accuracy": 0,
                    "adjusted": False,
                    "reason": "duplicate_submission",
                    "updated_at": existing_answer.updated_at,
                },
                "answered_questions": db.query(models.AssessmentAnswer).filter(models.AssessmentAnswer.attempt_id == attempt.id).count(),
                "total_questions": MAX_TOTAL_QUESTIONS,
                "completed_skills": _completed_skills(db, user, attempt.id),
                "next_question": _serialize_attempt(db, attempt).get("current_question"),
                "assessment_complete": attempt.status == "evaluated",
                "final_skill_profile": _serialize_attempt(db, attempt).get("final_skill_profile", {}),
                "result": None,
                "duplicate_submission": True,
            }
        raise HTTPException(status_code=409, detail="Question already answered")

    _validate_answer(question, attempt_question, answer)
    answer_row = models.AssessmentAnswer(
        attempt_id=attempt.id,
        attempt_question_id=attempt_question.id,
        question_id=question.id,
        answer_json=_dumps(answer),
        maximum_marks=attempt_question.maximum_marks,
        submission_hash=normalized_hash,
    )
    db.add(answer_row)
    db.flush()
    marks, is_correct, details = _score_answer(question, attempt_question, answer_row)
    graded_correct = bool(is_correct) if is_correct is not None else marks >= (attempt_question.maximum_marks * 0.75)
    difficulty_adjustment = evaluate_difficulty(
        db,
        user.id,
        question.skill or question.skill_tag,
        graded_correct,
        context={
            "source": "assessment",
            "attempt_id": attempt.id,
            "question_id": question.id,
            "event_id": f"assessment:{attempt.id}:{attempt_question.id}",
        },
        commit=False,
    )
    answer_row.marks_awarded = round(float(marks), 2)
    answer_row.is_correct = is_correct
    answer_row.normalized_answer_json = _dumps({"normalized": details.get("normalized_answer")})
    answer_row.scoring_details_json = _dumps(details)
    answer_row.updated_at = datetime.now(timezone.utc)
    db.add(answer_row)

    # Advance to the next question before returning, or finalize if the bank is exhausted.
    next_skill = _next_skill_to_assess(db, user, attempt.id)
    next_question_payload = None
    if next_skill is not None:
        next_candidates = _candidate_questions(
            db,
            user,
            attempt.id,
            next_skill,
            _skill_difficulty_snapshot(db, user)[next_skill],
        )
        if next_candidates:
            next_attempt_question = _create_attempt_question(
                db,
                attempt,
                next_candidates[0],
                translation_language=user.comfortable_language,
            )
            next_question_payload = _question_payload(
                next_attempt_question,
                next_candidates[0],
                db=db,
                translation_language=user.comfortable_language,
            )

    db.commit()

    if next_question_payload is None:
        result = submit_attempt(db, user, attempt.id)
        return {
            "correct": graded_correct,
            "skill": normalize_question_skill(question.skill or question.skill_tag),
            "question_id": question.id,
            "attempt_question_id": attempt_question.id,
            "difficulty": difficulty_adjustment,
            "answered_questions": db.query(models.AssessmentAnswer).filter(models.AssessmentAnswer.attempt_id == attempt.id).count(),
            "total_questions": MAX_TOTAL_QUESTIONS,
            "completed_skills": _completed_skills(db, user, attempt.id),
            "next_question": None,
            "assessment_complete": True,
            "final_skill_profile": _serialize_attempt(db, attempt).get("final_skill_profile", {}),
            "result": result,
            "duplicate_submission": False,
        }

    return {
        "correct": graded_correct,
        "skill": normalize_question_skill(question.skill or question.skill_tag),
        "question_id": question.id,
        "attempt_question_id": attempt_question.id,
        "difficulty": difficulty_adjustment,
        "answered_questions": db.query(models.AssessmentAnswer).filter(models.AssessmentAnswer.attempt_id == attempt.id).count(),
        "total_questions": MAX_TOTAL_QUESTIONS,
        "completed_skills": _completed_skills(db, user, attempt.id),
        "next_question": next_question_payload,
        "assessment_complete": False,
        "final_skill_profile": _serialize_attempt(db, attempt).get("final_skill_profile", {}),
        "result": None,
        "duplicate_submission": False,
    }


def complete_assessment(db: Session, user: models.User, attempt_id: int):
    attempt = (
        db.query(models.AssessmentAttempt)
        .filter(models.AssessmentAttempt.id == attempt_id, models.AssessmentAttempt.user_id == user.id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.status != "in_progress":
        return submit_attempt(db, user, attempt.id)

    current = _current_attempt_question(db, attempt.id)
    if current is not None:
        raise HTTPException(status_code=409, detail="Current question must be answered before completion")
    return submit_attempt(db, user, attempt.id)
