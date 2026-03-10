#!/usr/bin/env python3
"""
Полная очистка Google Таблицы (только данных) с сохранением структуры.

Что делает:
- очищает все ячейки листа, кроме заголовка;
- записывает в строку 1 актуальные заголовки из sheets.SHEET_HEADERS;
- оставляет таблицу пустой, чтобы монитор заново заполнял её новыми данными.

Запуск:
  source .venv/bin/activate
  python wipe_sheet.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from sheets import _get_client, SHEET_HEADERS


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

    # Полностью очищаем лист
    worksheet.clear()

    # Восстанавливаем заголовок в A1:I1
    worksheet.update("A1:I1", [SHEET_HEADERS], value_input_option="USER_ENTERED")

    print("Таблица очищена. Заголовки восстановлены, данных больше нет.")
    print("Теперь можно запускать монитор заново: python main.py")


if __name__ == "__main__":
    main()

