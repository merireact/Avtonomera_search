"""
Очистка таблицы от дубликатов номеров.

Если в таблице один и тот же номер записан по-разному, например:
  - A200MA977
  - 200MA977
  - A 200 MA 977
и т.п., то это считается одним номером.

Скрипт оставляет в таблице только первую встреченную строку для каждого номера,
а все последующие дубликаты удаляет.

Запуск:
    python cleanup_duplicate_plates_in_sheet.py
"""

from __future__ import annotations

import sys
from typing import Dict, List

import config
from plate_detector import canonical_plate_key, _normalize_plate
from sheets import _get_client


def _normalize_for_sheet(plate: str) -> str:
    """
    Нормализация номера для сравнения в таблице:
    убираем пробелы/дефисы, приводим к русским буквам и
    учитываем вариант без первой буквы (A200MA977 == 200MA977).
    """
    base = _normalize_plate(plate)
    return canonical_plate_key(base)


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

    rows: List[List[str]] = worksheet.get_all_values()
    if len(rows) <= 1:
        print("В таблице нет данных (только заголовок).")
        return

    first_row_for_plate: Dict[str, int] = {}
    to_delete: List[int] = []

    # Проходим по строкам, начиная со второй (первая — заголовок).
    for i in range(1, len(rows)):
        row = rows[i]
        if not row:
            continue
        raw_plate = (row[0] if len(row) > 0 else "") or ""
        norm_plate = _normalize_for_sheet(raw_plate)
        if not norm_plate:
            continue

        # gspread: строки нумеруются с 1; строка 1 — заголовок, данные с 2.
        sheet_row_index = i + 1

        if norm_plate in first_row_for_plate:
            # Это дубликат уже встречавшегося номера — помечаем на удаление.
            to_delete.append(sheet_row_index)
        else:
            first_row_for_plate[norm_plate] = sheet_row_index

    if not to_delete:
        print("Дубликатов номеров в таблице не найдено.")
        return

    # Один batch_update вместо удаления по одной строке — иначе лимит 429 (Write requests per minute).
    to_delete.sort(reverse=True)
    sheet_id = worksheet._properties.get("sheetId")
    requests = [
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
        for idx in to_delete
    ]
    sh.batch_update({"requests": requests})
    print(f"Удалено строк с дублирующимися номерами: {len(to_delete)}")


if __name__ == "__main__":
    main()

