"""
Plate detector module for Russian car license plates.

Detects plate numbers in text using multiple regex patterns.
Supports formats with/without spaces/dashes and with/without region letter.
"""

import re
from typing import List

# Optional separator between groups (space, dash, dot, comma, slash)
_SEP = r"[\s\-\.\,\/]*"

# 1 letter (region) + 3 digits + 2 letters + 2 or 3 digits — основной формат
# Примеры: A777AA77, В123СТ77, а 123 вс 77
PATTERN_FULL = re.compile(
    r"[A-ZА-Яa-zа-я]" + _SEP + r"\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2,3}",
    re.UNICODE,
)

# 3 digits + 2 letters + 2 or 3 digits — без первой буквы региона
# Примеры: 777АА77, 123СТ77
PATTERN_NO_REGION = re.compile(
    r"\b\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2,3}\b",
    re.UNICODE,
)

# 1 letter + 3 digits + 2 letters + 2 digits — строго 2 цифры в конце (часто в тексте)
PATTERN_STRICT_END = re.compile(
    r"\b[A-ZА-Яa-zа-я]" + _SEP + r"\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2}\b",
    re.UNICODE,
)

# Все паттерны по порядку (сначала полный, потом без региона)
ALL_PATTERNS = [PATTERN_FULL, PATTERN_NO_REGION, PATTERN_STRICT_END]


def _normalize_plate(raw: str) -> str:
    """Убираем пробелы/дефисы и приводим к одному регистру."""
    cleaned = re.sub(r"[\s\-\.]+", "", raw).upper()
    return cleaned


def _looks_like_plate(s: str) -> bool:
    """Отсекаем очевидные не-номера (только цифры, слишком короткие и т.д.)."""
    if len(s) < 6 or len(s) > 12:
        return False
    # Должны быть и буквы, и цифры
    has_letter = any(c.isalpha() for c in s)
    has_digit = any(c.isdigit() for c in s)
    return has_letter and has_digit


def find_plates(text: str | None) -> List[str]:
    """
    Find all Russian-style license plate numbers in the given text.

    Uses several patterns to catch:
    - Full format: A777AA77, В123СТ77, а 123 вс 77
    - With spaces/dashes: A 777 AA 77, А-123-СТ-77
    - Without region letter: 777АА77, 123СТ77

    Args:
        text: Raw message text (can be None or empty).

    Returns:
        List of unique plate strings found, normalized (no spaces, uppercase).
    """
    if not text or not text.strip():
        return []

    seen: set[str] = set()
    result: List[str] = []

    for pattern in ALL_PATTERNS:
        for m in pattern.findall(text):
            normalized = _normalize_plate(m)
            if _looks_like_plate(normalized) and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)

    return result
