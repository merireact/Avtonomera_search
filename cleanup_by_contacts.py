#!/usr/bin/env python3
"""
Удалить из Google Таблицы все строки с номерами, которые относятся к указанным телефонам/аккаунтам.

Ищем контакты в:
  - колонке «Отправитель» (D),
  - колонке «Телефон» (I),
  - тексте сообщения (F).

Если в строке встречается любой из шаблонов, строка удаляется из таблицы.

Запуск:
  source .venv/bin/activate
  python cleanup_by_contacts.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from sheets import _get_client
from phone_utils import normalize_phone


# Список перекупов: телефоны и username'ы, переданные пользователем
RAW_CONTACTS = [
    "+79267840000",
    "+79165613040",
    "@soo779",
    "+79995999177",
    "@A977AV",
    "+79200003838",
    "89639220006",
    "+79672275932",
    "89692777778",
    "@Ruslan_lev77",
    "@zverev023",
    "@NomernoySSS",
    "@rus_krsk",
    "@EDUARD555",
    "8(916)561-30-40",
    "@Igor77BBB",
    "@nomerokmsk797",
    "+79957970888",
    "+79269263833",
    "@avto_nomera97",
    "@avtoznaki",
    "@AUTOMOBILE_77",
    "@RusRus77777",
    "@VIPHOMEP77",
    "+79857194880",
    "@avtonomera_vip",
    "@m052mm52",
    "89660525222",
    "+79800815555",
    "@O070BM",
    "@b_konstantin",
    "+79859784591",
    "@vladimirnomer",
    "@NomernoySSS",
    "8-967-777-10-55",
    "@Ramzes_64",




]


def _normalize_username(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if not s.startswith("@"):
        s = "@" + s
    return s.lower()


PHONE_PATTERNS: set[str] = set()
USERNAME_PATTERNS: set[str] = set()
for item in RAW_CONTACTS:
    if "@" in item:
        USERNAME_PATTERNS.add(_normalize_username(item))
    else:
        p = normalize_phone(item)
        if p:
            PHONE_PATTERNS.add(p)


def _digits_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def row_matches(row: list[str]) -> bool:
    """
    Проверка, нужно ли удалять строку.
    row: список значений (как из get_all_values()).
    Колонки:
      0: Номер
      3: Отправитель
      5: Текст сообщения
      8: Телефон
    """
    sender = (row[3] if len(row) > 3 else "") or ""
    message = (row[5] if len(row) > 5 else "") or ""
    phone_cell = (row[8] if len(row) > 8 else "") or ""

    sender_norm = _normalize_username(sender)
    message_lower = message.lower()

    # Сначала проверяем username'ы
    for u in USERNAME_PATTERNS:
        if sender_norm == u:
            return True
        if u in message_lower:
            return True

    # Проверяем телефоны
    # 1) Ячейка «Телефон»
    if phone_cell:
        phone_norm = normalize_phone(phone_cell)
        if phone_norm and phone_norm in PHONE_PATTERNS:
            return True

    # 2) Телефоны в самом тексте (по цифрам)
    digits_message = _digits_only(message)
    for p in PHONE_PATTERNS:
        digits_pat = _digits_only(p)
        if digits_pat and digits_pat in digits_message:
            return True

    return False


def main() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        print("GOOGLE_SPREADSHEET_ID не задан. Проверьте .env.")
        sys.exit(1)

    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except Exception as e:
        print("Не удалось открыть таблицу или лист:", e)
        sys.exit(1)

    rows = worksheet.get_all_values()
    if len(rows) <= 1:
        print("В таблице нет данных (только заголовок).")
        return

    to_delete: list[int] = []
    for i in range(1, len(rows)):  # пропускаем заголовок (строка 1)
        row = rows[i]
        if row_matches(row):
            to_delete.append(i + 1)  # в gspread строки 1-based

    if not to_delete:
        print("Строк для удаления не найдено по указанным телефонам/аккаунтам.")
        return

    # Удаляем строки одним batch_update, чтобы не упираться в лимит 429
    to_delete.sort(reverse=True)
    sheet_id = worksheet._properties.get("sheetId")
    requests = []
    for idx in to_delete:
        requests.append(
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": idx - 1,
                        "endIndex": idx,
                    }
                }
            }
        )

    sh.batch_update({"requests": requests})
    print(f"Удалено строк из таблицы: {len(to_delete)}")


if __name__ == "__main__":
    main()

