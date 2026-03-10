#!/usr/bin/env python3
"""
Обновить колонку «Номер» (A) в Google Таблице: заменить латинские буквы на русские.

Все номера в таблице будут приведены к одному виду: без пробелов/дефисов,
верхний регистр, буквы только кириллица (А, В, Е, К, М, Н, О, Р, С, Т, У, Х).

Запуск:
    source .venv/bin/activate
    python normalize_plates_in_sheet.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from plate_detector import _normalize_plate
from sheets import _get_client


def main() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        print("GOOGLE_SPREADSHEET_ID не задан. Проверьте .env.")
        sys.exit(1)

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

    col_a = worksheet.col_values(1)
    if not col_a or len(col_a) <= 1:
        print("В таблице нет данных (только заголовок или пусто).")
        return

    updates: list[tuple[int, str]] = []  # (номер строки 1-based, новое значение)
    for i in range(1, len(col_a)):
        raw = (col_a[i] or "").strip()
        if not raw:
            continue
        normalized = _normalize_plate(raw)
        if normalized != raw:
            updates.append((i + 1, normalized))  # строка в листе 1-based

    if not updates:
        print("Все номера уже записаны русскими буквами. Ничего менять не нужно.")
        return

    print(f"Нужно обновить {len(updates)} ячеек в колонке A (латиница → кириллица).")

    batch_size = 200
    for start in range(0, len(updates), batch_size):
        chunk = updates[start : start + batch_size]
        data = [{"range": f"A{row}", "values": [[value]]} for row, value in chunk]
        worksheet.batch_update(data, value_input_option="USER_ENTERED")
        print(f"  Обновлено строк A{chunk[0][0]}–A{chunk[-1][0]}.")

    print("Готово. Все номера в таблице приведены к русским буквам.")


if __name__ == "__main__":
    main()
