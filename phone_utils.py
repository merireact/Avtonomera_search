"""
Утилиты для работы с телефонными номерами.

Используются как при разборе сообщений (telegram_monitor), так и при отправке
сообщений из таблицы (send_sheet_messages).
"""

from __future__ import annotations

import re
from typing import Optional


def normalize_phone(phone: str) -> str:
    """
    Привести номер к формату +79XXXXXXXXX для Telegram.

    Более терпимая нормализация:
      - выкидывает всё, кроме цифр;
      - если цифр больше 11 — берём последние 11 (как в «...тел. +7... / WhatsApp»);
      - поддерживает варианты:
        +7 9XX XXX-XX-XX, 8 9XX XXX-XX-XX, 9XX XXX-XX-XX.
    Если не удаётся получить осмысленный российский номер — возвращает пустую строку.
    """
    if not phone or not phone.strip():
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return ""
    # Если цифр слишком много — берём хвост, там обычно сам номер
    if len(digits) > 11:
        digits = digits[-11:]

    # Приводим к 11-значному формату, начинающемуся с 7
    if len(digits) == 11:
        if digits.startswith("8"):
            digits = "7" + digits[1:]
        elif digits.startswith("9"):
            digits = "7" + digits
        elif not digits.startswith("7"):
            # Берём последние 10 цифр как номер без кода и добавляем 7
            digits = "7" + digits[-10:]
    elif len(digits) == 10:
        # 9XXXXXXXXX или что-то вроде того
        if not digits.startswith("7"):
            digits = "7" + digits

    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    return ""


_PHONE_CANDIDATE_RE = re.compile(r"[+0-9][0-9()\-\s,\u00A0]{6,32}")


def extract_first_phone(text: str) -> Optional[str]:
    """
    Найти первый похожий на телефон фрагмент в тексте и вернуть нормализованный номер (+79...).
    Если ни один фрагмент не проходит нормализацию — вернуть None.
    """
    if not text:
        return None
    for match in _PHONE_CANDIDATE_RE.finditer(text):
        candidate = match.group(0)
        norm = normalize_phone(candidate)
        if norm.startswith("+7") and len(norm) == 12:
            return norm
    return None


_USERNAME_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")


def extract_first_username(text: str) -> Optional[str]:
    """
    Найти первое упоминание Telegram-аккаунта вида @username в тексте.
    Возвращает строку '@username' либо None, если ничего не найдено.
    """
    if not text:
        return None
    m = _USERNAME_RE.search(text)
    if not m:
        return None
    return "@" + m.group(1)


