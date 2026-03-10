#!/usr/bin/env python3
"""
Обновить заголовки в Google Таблице: добавить колонки H «Отправить» и I «Телефон» в первую строку.

Запустите один раз, если таблица была создана до появления этих колонок:
  python update_sheet_headers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from sheets import SHEET_HEADERS, _get_client


def main() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        print("GOOGLE_SPREADSHEET_ID не задан. Задайте в .env")
        sys.exit(1)
    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except FileNotFoundError as e:
        print("Ошибка: не найден файл учётных данных Google.", e)
        sys.exit(1)
    except Exception as e:
        print("Ошибка открытия таблицы:", e)
        sys.exit(1)

    # Обновить первую строку — полный набор заголовков A1:I1
    worksheet.update("A1:I1", [SHEET_HEADERS], value_input_option="USER_ENTERED")
    print("Заголовки обновлены: A1:I1 =", SHEET_HEADERS)
    print("Колонки H «Отправить» и I «Телефон» добавлены в таблицу.")


if __name__ == "__main__":
    main()
