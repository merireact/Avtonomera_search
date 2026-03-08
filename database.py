"""
Database module for storing detected plate records.

Handles SQLite persistence and CSV export. Ensures no duplicate
entries for the same plate + message (idempotent inserts).
"""

import csv
import sqlite3
from pathlib import Path
from typing import Any

from config import CSV_PATH, DATABASE_PATH


# SQLite table schema matching the required structure
TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS plates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,
    source_channel TEXT NOT NULL,
    sender TEXT,
    message TEXT,
    message_link TEXT,
    date TEXT NOT NULL,
    UNIQUE(plate, message)
)
"""


def get_connection() -> sqlite3.Connection:
    """Create and return a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def init_database() -> None:
    """Create the plates table if it does not exist."""
    conn = get_connection()
    try:
        conn.execute(TABLE_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_plate(
    plate: str,
    source_channel: str,
    sender: str | None,
    message: str | None,
    message_link: str | None,
    date: str,
) -> bool:
    """
    Insert a plate record if not already present (same plate + message).

    Returns:
        True if a new row was inserted, False if it was a duplicate.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO plates
            (plate, source_channel, sender, message, message_link, date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (plate, source_channel, sender or "", message or "", message_link or "", date),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_all_rows() -> list[dict[str, Any]]:
    """Все записи из БД (id, plate, source_channel, sender, message, message_link, date)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, plate, source_channel, sender, message, message_link, date FROM plates"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_by_ids(ids: list[int]) -> int:
    """Удалить записи по списку id. Возвращает количество удалённых."""
    if not ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(ids))
        cursor = conn.execute(
            f"DELETE FROM plates WHERE id IN ({placeholders})",
            tuple(ids),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_plates(plates: set[str]) -> int:
    """
    Удалить из БД все записи с номерами из множества plates.
    Возвращает количество удалённых строк.
    """
    if not plates:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(plates))
        cursor = conn.execute(
            f"DELETE FROM plates WHERE plate IN ({placeholders})",
            tuple(plates),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def append_to_csv(row: dict[str, Any]) -> None:
    """
    Append a single record to the CSV file.
    Creates the file with headers if it does not exist.
    """
    file_exists = CSV_PATH.exists()
    fieldnames = ["plate", "source_channel", "sender", "message", "message_link", "date"]

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fieldnames})
