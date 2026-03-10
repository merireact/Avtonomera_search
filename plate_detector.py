"""
Plate detector module for Russian car license plates.

Detects plate numbers in text using multiple regex patterns.
Supports formats with/without spaces/dashes and with/without region letter.
"""

import re
from typing import List

_SEP = r"[\s\-\.\,\/]*"

# Карта похожих латинских букв в русские,
# чтобы в результате всегда были русские буквы (А, В, М, Т, У, Х и т.д.).
_LATIN_TO_CYR = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "E": "Е",
        "K": "К",
        "M": "М",
        "H": "Н",
        "O": "О",
        "P": "Р",
        "C": "С",
        "T": "Т",
        "Y": "У",
        "X": "Х",
    }
)

PATTERN_FULL = re.compile(
    r"[A-ZА-Яa-zа-я]" + _SEP + r"\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2,3}",
    re.UNICODE,
)

PATTERN_NO_REGION = re.compile(
    r"\b\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2,3}\b",
    re.UNICODE,
)

PATTERN_STRICT_END = re.compile(
    r"\b[A-ZА-Яa-zа-я]" + _SEP + r"\d{3}" + _SEP + r"[A-ZА-Яa-zа-я]{2}" + _SEP + r"\d{2}\b",
    re.UNICODE,
)

ALL_PATTERNS = [PATTERN_FULL, PATTERN_NO_REGION, PATTERN_STRICT_END]


def _normalize_plate(raw: str) -> str:
    """
    Убираем пробелы/дефисы, приводим к верхнему регистру
    и переводим похожие латинские буквы в русские.
    """
    cleaned = re.sub(r"[\s\-\.]+", "", raw or "").upper()
    cleaned = cleaned.translate(_LATIN_TO_CYR)
    return cleaned


def canonical_plate_key(plate: str) -> str:
    """
    Ключ для сравнения номеров.

    A200MA977 и 200MA977 считаются одним номером:
    обрезаем первую букву, если дальше идёт 3 цифры + 2 буквы + 2–3 цифры.
    """
    p = (plate or "").strip()
    if len(p) >= 7 and p[0].isalpha() and p[1:4].isdigit() and p[4:6].isalpha():
        return p[1:]
    return p


def get_region_code(plate: str) -> str | None:
    """
    Извлечь код региона из номера (последние 2 или 3 цифры).
    Номер должен быть нормализован (без пробелов, верхний регистр).
    Примеры: А771СА797 -> 797, В123СТ77 -> 77.
    """
    if not plate or not plate[-1].isdigit():
        return None
    i = len(plate) - 1
    while i >= 0 and plate[i].isdigit():
        i -= 1
    digits = plate[i + 1 :]
    return digits if len(digits) in (2, 3) else None


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

    seen_keys: set[str] = set()
    result: List[str] = []

    for pattern in ALL_PATTERNS:
        for m in pattern.findall(text):
            normalized = _normalize_plate(m)
            if not _looks_like_plate(normalized):
                continue
            key = canonical_plate_key(normalized)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result.append(normalized)

    return result
