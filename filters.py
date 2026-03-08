"""
Общая логика фильтрации перекупов: не добавлять номера из таких сообщений
и удалять уже попавшие в таблицу.
"""

import re
from typing import Optional

import config


def is_blocked_sender(sender_username: Optional[str]) -> bool:
    """Отправитель в списке перекупов — его номера не берём."""
    if not sender_username:
        return False
    username_clean = (sender_username or "").lstrip("@").strip().lower()
    return any(s.strip().lower() == username_clean for s in config.BLOCKED_SENDERS)


# Паттерн: строка содержит номер и потом дефис/тире и цену (много цифр)
# Например: Х539ХХ150-250000  или  Е956ХК797-15000
_RE_LINE_PLATE_PRICE = re.compile(
    r"[A-ZА-Яa-zа-я]\d{3}[A-ZА-Яa-zа-я]{2}\d{2,3}\s*[-–—]\s*\d",
    re.UNICODE,
)


def is_reseller_list_message(text: str) -> bool:
    """
    Сообщение похоже на список перекупов:
    - заголовки «СПИСОК», «ЦЕНА БЕЗ ОФОРМЛЕНИЯ»;
    - или много строк формата «номер-цена» (например Х539ХХ150-250000).
    """
    if not text or len(text) < 30:
        return False
    t = text.upper()
    # Явные маркеры списка
    if "СПИСОК" in t and "ЦЕНА" in t:
        return True
    if "ЦЕНА БЕЗ ОФОРМЛЕНИЯ" in t:
        return True
    # Много строк «номер-цена» — типичный прайс перекупа
    lines = text.splitlines()
    price_lines = sum(1 for line in lines if _RE_LINE_PLATE_PRICE.search(line))
    if price_lines >= 3:
        return True
    return False


def is_message_too_long(text: str) -> bool:
    """Текст сообщения слишком длинный — не берём номера."""
    return len(text or "") > config.MAX_MESSAGE_LENGTH_FOR_PLATES


def should_skip_message(text: str, sender_username: Optional[str]) -> bool:
    """Нужно ли пропустить сообщение (не добавлять из него номера)."""
    return (
        is_blocked_sender(sender_username)
        or is_message_too_long(text)
        or is_reseller_list_message(text)
    )
