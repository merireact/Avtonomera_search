#!/usr/bin/env python3
"""
Разовая до-запись телефонов в Google Таблицу для старых строк.

Берёт все записи из БД (plates.db), вытаскивает телефон из текста сообщения
и подставляет его в колонку I «Телефон» для соответствующей строки в таблице,
если там сейчас пусто.

Соответствие строки: по паре (Номер, Ссылка на сообщение).

Запуск (в папке проекта):

    source .venv/bin/activate
    python backfill_phones_in_sheet.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from database import get_all_rows
from phone_utils import extract_first_phone, normalize_phone
from sheets import _get_client


def _norm_plate(s: str) -> str:
    """Нормализация номера (так же, как в sheets._norm_plate)."""
    return (s or "").replace(" ", "").replace("-", "").upper().strip()


def main() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        print("GOOGLE_SPREADSHEET_ID не задан. Проверьте .env.")
        sys.exit(1)

    # Подключаемся к таблице
    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except FileNotFoundError as e:
        print("Ошибка: не найден файл google_credentials.json или путь из GOOGLE_CREDENTIALS_PATH.", e)
        sys.exit(1)
    except Exception as e:
        print("Не удалось открыть таблицу или лист:", e)
        sys.exit(1)

    rows_sheet = worksheet.get_all_values()
    if len(rows_sheet) <= 1:
        print("В таблице нет данных (только заголовок).")
        return

    # Построим карту: (plate_norm, link) -> индекс строки листа (1-based)
    sheet_index: dict[tuple[str, str], int] = {}
    for i in range(1, len(rows_sheet)):  # пропускаем заголовок (строка 1)
        row = rows_sheet[i]
        plate_cell = _norm_plate(row[0] if len(row) > 0 else "")
        link_cell = (row[2] if len(row) > 2 else "").strip()
        if plate_cell and link_cell:
            sheet_row_num = i + 1  # 1-based
            sheet_index[(plate_cell, link_cell)] = sheet_row_num

    if not sheet_index:
        print("Не найдено ни одной строки с (Номер, Ссылка) в таблице.")
        return

    # Берём все записи из БД
    db_rows: list[dict[str, Any]] = get_all_rows()
    if not db_rows:
        print("В БД нет записей.")
        return

    updates: list[tuple[int, str]] = []  # (sheet_row_num, phone)

    for rec in db_rows:
        plate = _norm_plate(rec.get("plate", ""))
        link = (rec.get("message_link") or "").strip()
        if not plate or not link:
            continue
        key = (plate, link)
        sheet_row_num = sheet_index.get(key)
        if not sheet_row_num:
            continue  # этой строки нет в таблице

        # В таблице уже может быть телефон — не перезатираем
        row_sheet = rows_sheet[sheet_row_num - 1]
        phone_cell = (row_sheet[8] if len(row_sheet) > 8 else "").strip()  # колонка I = индекс 8
        # Если в ячейке уже нормальный номер — не трогаем.
        # Если там мусор/старый чекбокс (TRUE и т.п.), попробуем перезаписать.
        from phone_utils import normalize_phone as _norm

        if phone_cell and _norm(phone_cell):
            continue

        text = rec.get("message") or ""
        phone = extract_first_phone(text)
        if not phone:
            continue

        phone_norm = normalize_phone(phone)
        if not phone_norm:
            continue

        updates.append((sheet_row_num, phone_norm))

    if not updates:
        print("Нет телефонов для добавления: либо всё уже заполнено, либо номера не найдены в текстах.")
        return

    # Обновляем ячейки пакетами, чтобы не бить по лимитам
    print(f"Найдено строк для заполнения телефонами: {len(updates)}")
    batch_size = 50
    for i in range(0, len(updates), batch_size):
        chunk = updates[i : i + batch_size]
        data = [
            {
                "range": f"I{row_num}",
                "values": [[phone]],
            }
            for (row_num, phone) in chunk
        ]
        worksheet.batch_update(data, value_input_option="USER_ENTERED")
        print(f"Обновлено строк: {i + len(chunk)} / {len(updates)}")

    print("Готово. Колонка «Телефон» заполнена для старых строк, где номер удалось найти в тексте.")


if __name__ == "__main__":
    main()

