#!/usr/bin/env python3
"""
Синхронизация БД → Google Таблица.

Все записи из plates.db, которых ещё нет в таблице (по паре номер + ссылка),
добавляются в лист. Запускайте после сбоев (429, перезапись строки), когда
в БД уже есть номера, а в таблице — нет.

Запуск: python sync_db_to_sheet.py
"""

import time
import config
from database import get_all_rows
from plate_detector import get_region_code
from sheets import get_existing_plate_links, append_plate_row, _norm_plate


def main() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        print("GOOGLE_SPREADSHEET_ID не задан. Задайте в .env или config.")
        return

    rows = get_all_rows()
    if not rows:
        print("В БД нет записей.")
        return

    print("Загружаю список строк из таблицы...")
    existing = get_existing_plate_links()
    print(f"В таблице уже есть {len(existing)} записей (номер + ссылка).")

    to_add: list[dict] = []
    for r in rows:
        plate = (r.get("plate") or "").strip()
        link = (r.get("message_link") or "").strip()
        if not plate:
            continue
        if get_region_code(plate) not in config.ALLOWED_REGION_CODES:
            continue
        key = (_norm_plate(plate), link)
        if key not in existing:
            to_add.append(r)

    if not to_add:
        print("Все записи из БД уже есть в таблице. Ничего не добавляю.")
        return

    print(f"Добавлю в таблицу {len(to_add)} записей...")
    ok = 0
    for i, r in enumerate(to_add):
        row = {
            "plate": r.get("plate", ""),
            "source_channel": r.get("source_channel", ""),
            "message_link": r.get("message_link", ""),
            "sender": r.get("sender", ""),
            "date": r.get("date", ""),
            "message": r.get("message", ""),
        }
        if append_plate_row(row):
            ok += 1
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(to_add)}...")
        # Небольшая пауза, чтобы не упереться в лимит Google API
        if i < len(to_add) - 1:
            time.sleep(0.3)
    print(f"Готово. Добавлено строк: {ok}.")


if __name__ == "__main__":
    main()
