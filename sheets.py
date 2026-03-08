"""
Google Sheets integration: append detected plates to a spreadsheet.

Requires service account JSON key and GOOGLE_SPREADSHEET_ID in config.
"""

import logging
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("sheets")

# Header row for the sheet
SHEET_HEADERS = [
    "Номер",
    "Канал",
    "Ссылка",
    "Отправитель",
    "Дата",
    "Текст сообщения",
    "Сообщение для клиента",
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
    Append one plate record to the configured Google Sheet.

    Expects row with keys: plate, source_channel, message_link, sender, date, message.
    Creates the sheet and writes headers if the sheet is empty.

    Returns:
        True if appended successfully, False if disabled or error.
    """
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
        # Check if first row is empty → write full header; or has old 6 columns → add 7th header
        first_cell = worksheet.cell(1, 1).value
        if not first_cell or first_cell.strip() == "":
            worksheet.append_row(SHEET_HEADERS, value_input_option="USER_ENTERED")
        else:
            # Если заголовок старый (6 колонок), дописать "Сообщение для клиента" в G1
            col7 = worksheet.cell(1, 7).value
            if not col7 or col7.strip() == "":
                worksheet.update_cell(1, 7, "Сообщение для клиента")

        plate = row.get("plate", "")
        values = [
            plate,
            row.get("source_channel", ""),
            row.get("message_link", ""),
            row.get("sender", ""),
            row.get("date", ""),
            (row.get("message") or "")[:500],  # limit message length
            _client_message(plate) if plate and not plate.startswith("[") else "",
        ]
        worksheet.append_row(values, value_input_option="USER_ENTERED")
        logger.info("Appended plate to Google Sheet: %s", row.get("plate"))
        return True
    except Exception as e:
        logger.exception("Failed to append to Google Sheet: %s", e)
        return False
