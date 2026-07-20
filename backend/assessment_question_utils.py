from __future__ import annotations

import random
import re
import unicodedata
from collections import Counter
from typing import Any


TERMINAL_PUNCTUATION_PATTERN = re.compile(r"[.!?。！？।]+$")
TOKEN_EDGE_PUNCTUATION_PATTERN = re.compile(r"^[\s\"'“”‘’(\[\{]+|[\s\"'“”‘’)\]\},.;:!?ã€。ï¼ï¼Ÿà¥¤à¥¥]+$")
VIRAMA_CHARACTERS = {"्", "்", "్", "್"}


def normalize_sentence_text(
    value: str,
    *,
    case_sensitive: bool = False,
    allow_terminal_punctuation: bool = True,
) -> str:
    text = unicodedata.normalize("NFC", value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    if allow_terminal_punctuation:
        text = TERMINAL_PUNCTUATION_PATTERN.sub("", text).strip()
    if not case_sensitive:
        text = text.casefold()
    return text


def grapheme_clusters(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text or "")
    clusters: list[str] = []
    current = ""
    previous_was_virama = False
    for character in normalized:
        if not character.strip():
            if current:
                clusters.append(current)
                current = ""
            previous_was_virama = False
            continue

        category = unicodedata.category(character)
        if current and (category.startswith("M") or previous_was_virama):
            current += character
        else:
            if current:
                clusters.append(current)
            current = character
        previous_was_virama = character in VIRAMA_CHARACTERS

    if current:
        clusters.append(current)
    return clusters


def build_letter_tiles(answer_text: str) -> list[dict[str, str]]:
    clusters = grapheme_clusters(answer_text)
    if not clusters:
        return []
    tiles = [{"id": f"tile_{index + 1}", "value": cluster} for index, cluster in enumerate(clusters)]
    random.SystemRandom().shuffle(tiles)
    return tiles


def build_word_tiles(sentence_text: str, translations: list[str | None] | None = None) -> list[dict[str, Any]]:
    tokens = sentence_word_tokens(sentence_text)
    if not tokens:
        return []

    tiles = [
        {
            "id": f"tile_{index + 1}",
            "value": token,
            "translation": translations[index] if translations and index < len(translations) else None,
            "original_order": index,
        }
        for index, token in enumerate(tokens)
    ]
    random.SystemRandom().shuffle(tiles)
    return tiles


def build_ordered_word_tiles(sentence_text: str, translations: list[str | None] | None = None) -> list[dict[str, Any]]:
    return sorted(build_word_tiles(sentence_text, translations), key=lambda tile: tile["original_order"])


def sentence_word_tokens(sentence_text: str | None) -> list[str]:
    normalized = unicodedata.normalize("NFC", sentence_text or "").replace("\r\n", " ").replace("\r", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return [token for token in normalized.split(" ") if token] if normalized else []


def normalize_sentence_token(token: str) -> str:
    normalized = unicodedata.normalize("NFC", token or "").strip().casefold()
    normalized = TOKEN_EDGE_PUNCTUATION_PATTERN.sub("", normalized).strip()
    return normalized


def normalized_token_multiset(tokens: list[str]) -> Counter[str]:
    return Counter(token for token in (normalize_sentence_token(token) for token in tokens) if token)


def word_tiles_match_sentence(tiles: list[dict[str, Any]] | None, sentence_text: str | None) -> bool:
    if not tiles:
        return False
    tile_tokens = [
        tile.get("value")
        for tile in tiles
        if isinstance(tile, dict) and isinstance(tile.get("id"), str) and isinstance(tile.get("value"), str)
    ]
    if len(tile_tokens) != len(tiles):
        return False
    sentence_tokens = sentence_word_tokens(sentence_text)
    return bool(sentence_tokens) and normalized_token_multiset(tile_tokens) == normalized_token_multiset(sentence_tokens)


def ordered_words_match_sentence(ordered_words: list[dict[str, Any]] | None, sentence_text: str | None) -> bool:
    if not ordered_words:
        return False
    sorted_words = sorted(
        (
            word
            for word in ordered_words
            if isinstance(word, dict)
            and isinstance(word.get("value"), str)
            and isinstance(word.get("original_order"), int)
        ),
        key=lambda word: word["original_order"],
    )
    if len(sorted_words) != len(ordered_words):
        return False
    joined = " ".join(word["value"] for word in sorted_words)
    return normalize_sentence_text(joined) == normalize_sentence_text(sentence_text or "")


def sentence_tile_answer(question: dict[str, Any]) -> str | None:
    correct = question.get("correct", {})
    if not isinstance(correct, dict):
        return None

    reference = correct.get("reference_text")
    if isinstance(reference, str) and reference.strip():
        return reference.strip()
    accepted = correct.get("accepted_answers")
    if isinstance(accepted, list):
        for item in accepted:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None
