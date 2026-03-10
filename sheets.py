"""
Google Sheets integration: append detected plates to a spreadsheet.

Requires service account JSON key and GOOGLE_SPREADSHEET_ID in config.
"""

import logging
import threading
from pathlib import Path
from typing import Any, Callable

import config
from plate_detector import canonical_plate_key, _normalize_plate as _normalize_plate_for_compare

logger = logging.getLogger("sheets")

# Один append в момент — иначе при массовом скане несколько записей могут попасть в одну строку
_append_lock = threading.Lock()
# Следующая строка для записи (1-based). None = ещё не считали с листа. Избегаем append_row — он может кэшировать и писать в одну строку.
_next_sheet_row: int | None = None

# Header row for the sheet
# Колонка H «Отправить»: поставить 1 или «да» — скрипт send_sheet_messages.py отправит сообщение в Telegram.
# Колонка I «Телефон»: если отправителя нет — можно указать номер (+79...) для поиска в Telegram.
SHEET_HEADERS = [
    "Номер",
    "Канал",
    "Ссылка",
    "Отправитель",
    "Дата",
    "Текст сообщения",
    "Сообщение для клиента",
    "Отправить",
    "Телефон",
]

# Шаблон сообщения для клиента: {НОМЕР} заменится на найденный номер
MESSAGE_TEMPLATE = (
    "Добрый день! Занимаемся продажей автономеров — можем продать ваш номер через нашу систему продаж "
    "и мы полностью берём на себя весь процесс переоформления.\n"
    "Чтобы понять, сможем ли работать по номеру {НОМЕР}, подскажите минимальную цену для реальной продажи."
)


def _client_message(plate: str) -> str:
    """Подставить номер в шаблон сообщения для клиента."""
    return MESSAGE_TEMPLATE.replace("{НОМЕР}", plate)


def get_client_message(plate: str) -> str:
    """Публичная функция: текст сообщения для клиента с подставленным номером."""
    return _client_message(plate)


def _get_client():
    """Lazy import and create gspread client from service account."""
    import gspread
    from google.oauth2.service_account import Credentials

    path = config.GOOGLE_CREDENTIALS_PATH
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {path}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(path), scopes=scopes)
    return gspread.authorize(creds)


def append_plate_row(row: dict[str, Any]) -> bool:
    """
    Добавить одну запись в таблицу. Пишем в явно вычисленную строку (не append_row),
    чтобы при массовой записи не перезаписывать одну и ту же строку и не лить лишние Read-запросы (429).
    """
    global _next_sheet_row
    if not config.GOOGLE_SPREADSHEET_ID:
        return False
    path = config.GOOGLE_CREDENTIALS_PATH
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        logger.debug("Google credentials not found; skipping Sheets.")
        return False

    with _append_lock:
        try:
            gc = _get_client()
            sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
            try:
                worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
            except Exception:
                worksheet = sh.add_worksheet(title=config.GOOGLE_SHEET_NAME, rows=1000, cols=10)
        except Exception as e:
            logger.warning("Google Sheet open failed: %s", e)
            return False

        try:
            # Один раз за сессию узнаём следующую свободную строку (один запрос — колонка A)
            if _next_sheet_row is None:
                col_a = worksheet.col_values(1)
                if not col_a or all(c.strip() == "" for c in col_a):
                    worksheet.update("A1:I1", [SHEET_HEADERS], value_input_option="USER_ENTERED")
                    _next_sheet_row = 2
                else:
                    _next_sheet_row = len(col_a) + 1
                logger.debug("Sheet next row set to %s", _next_sheet_row)

            plate = (row.get("plate", "") or "").strip()
            if plate:
                plate = _normalize_plate_for_compare(plate)  # всегда русские буквы в таблице
            values = [
                plate,
                row.get("source_channel", ""),
                row.get("message_link", ""),
                row.get("sender", ""),
                row.get("date", ""),
                (row.get("message") or "")[:500],
                _client_message(plate) if plate and not plate.startswith("[") else "",
                "",  # Отправить
                row.get("phone", ""),  # Телефон
            ]
            row_num = _next_sheet_row
            worksheet.update(
                f"A{row_num}:I{row_num}",
                [values],
                value_input_option="USER_ENTERED",
            )
            _next_sheet_row = row_num + 1
            logger.info("Appended plate to Google Sheet row %s: %s", row_num, row.get("plate"))
            return True
        except Exception as e:
            logger.exception("Failed to append to Google Sheet: %s", e)
            return False


def _norm_plate(s: str) -> str:
    """Нормализация номера для сравнения с учётом русских букв и варианта без первой буквы."""
    base = _normalize_plate_for_compare(s)
    return canonical_plate_key(base)


def get_existing_plate_links() -> set[tuple[str, str]]:
    """
    Прочитать таблицу и вернуть множество пар (нормализованный номер, ссылка на сообщение).
    Нужно для синхронизации: не добавлять в таблицу то, что уже есть.
    """
    if not config.GOOGLE_SPREADSHEET_ID:
        return set()
    path = config.GOOGLE_CREDENTIALS_PATH
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        return set()
    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
        rows = worksheet.get_all_values()
    except Exception as e:
        logger.warning("Could not read sheet for existing rows: %s", e)
        return set()
    result: set[tuple[str, str]] = set()
    for row in rows[1:]:
        if len(row) < 3:
            continue
        plate = _norm_plate((row[0] or "").strip())
        link = (row[2] or "").strip()
        if plate and link:
            result.add((plate, link))
    return result


def delete_rows_with_plates(plates: set[str]) -> int:
    """
    Удалить из таблицы все строки, в которых в колонке «Номер» (A) указан номер из plates.
    Возвращает количество удалённых строк. Удаление с конца, чтобы индексы не сбивались.
    """
    if not config.GOOGLE_SPREADSHEET_ID or not plates:
        return 0
    path = config.GOOGLE_CREDENTIALS_PATH
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        logger.warning("Google credentials not found; cannot clean sheet.")
        return 0

    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except Exception as e:
        logger.warning("Google Sheet open failed: %s", e)
        return 0

    try:
        # Все значения: первая строка — заголовки
        all_rows = worksheet.get_all_values()
        if len(all_rows) <= 1:
            return 0
        # Приведём список таргетных номеров к каноническому виду,
        # чтобы A200MA977 и 200MA977 считались одним номером.
        norm_target_plates = {
            canonical_plate_key(_normalize_plate_for_compare(p)) for p in plates
        }

        def norm(s: str) -> str:
            base = _normalize_plate_for_compare(s)
            return canonical_plate_key(base)

        to_delete: list[int] = []
        for i in range(1, len(all_rows)):
            row = all_rows[i]
            if not row:
                continue
            plate_cell = norm(row[0])
            if plate_cell in norm_target_plates:
                # gspread: row index 1-based; row 1 = header, data from row 2
                to_delete.append(i + 1)
        if not to_delete:
            return 0
        # Удаляем с конца, чтобы индексы не сдвигались
        to_delete.sort(reverse=True)
        for row_index in to_delete:
            worksheet.delete_rows(row_index)
        logger.info("Removed %d rows from Google Sheet (blocked plates).", len(to_delete))
        return len(to_delete)
    except Exception as e:
        logger.exception("Failed to delete rows from Google Sheet: %s", e)
        return 0


def delete_reseller_and_long_message_rows(
    is_row_bad: Callable[[dict[str, str]], bool],
) -> int:
    """
    Удалить строки, для которых is_row_bad(row) возвращает True.
    row — dict с ключами: plate, sender, message (значения из колонок Номер, Отправитель, Текст сообщения).
    Удаление с конца. Возвращает количество удалённых строк.
    """
    if not config.GOOGLE_SPREADSHEET_ID:
        return 0
    path = config.GOOGLE_CREDENTIALS_PATH
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        return 0
    try:
        gc = _get_client()
        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except Exception as e:
        logger.warning("Google Sheet open failed: %s", e)
        return 0
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) <= 1:
            return 0
        to_delete: list[int] = []
        for i in range(1, len(all_rows)):
            row = all_rows[i]
            plate = (row[0] if len(row) > 0 else "") or ""
            sender = (row[3] if len(row) > 3 else "") or ""
            message = (row[5] if len(row) > 5 else "") or ""
            if is_row_bad({"plate": plate, "sender": sender, "message": message}):
                to_delete.append(i + 1)
        if not to_delete:
            return 0
        to_delete.sort(reverse=True)
        for row_index in to_delete:
            worksheet.delete_rows(row_index)
        logger.info("Removed %d rows from Google Sheet (reseller/long message).", len(to_delete))
        return len(to_delete)
    except Exception as e:
        logger.exception("Failed to delete rows from Google Sheet: %s", e)
        return 0
