#!/usr/bin/env python3
"""
Отправка сообщений из Google Таблицы в Telegram.

Читает строки, в которых в колонке «Отправить» (H) стоит 1 или «да»,
берёт «Сообщение для клиента» (G) и отправляет:
  — по «Отправитель» (D): в личку @username (тот, кто написал в канале);
  — если отправителя нет — по «Телефон» (I): ищет пользователя в Telegram по номеру и отправляет.

Использует ту же пользовательскую сессию Telethon, что и монитор (не бота).
Запуск: python send_sheet_messages.py
"""

import asyncio
import logging
import random
import sys
from pathlib import Path

# проект в пути
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from sheets import _get_client, get_client_message
from telethon import TelegramClient
from telethon import functions, types
from phone_utils import normalize_phone

# Каналы, которым не пишем в личку как «отправителю»
IGNORED_SENDER_USERNAMES: set[str] = {
    "@runomer",
    "@regznak",
    "@avtonomera_moskva",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("send_sheet")


# Значения в колонке «Отправить», при которых отправляем (в т.ч. флажок = TRUE)
SEND_TRIGGERS = ("1", "да", "отправить", "yes", "true", "TRUE")
def _normalize_sender(sender: str) -> str:
    """Username для Telegram: с @ или без."""
    if not sender or not sender.strip():
        return ""
    s = sender.strip()
    if not s.startswith("@"):
        s = "@" + s
    return s


async def _send_by_username(client: TelegramClient, username: str, text: str) -> str | None:
    """Отправить сообщение по @username. Возвращает None при успехе, иначе строку ошибки."""
    try:
        await client.send_message(username, text)
        return None
    except Exception as e:
        return str(e)


async def _send_by_phone(client: TelegramClient, phone: str, text: str) -> str | None:
    """
    Найти пользователя по номеру телефона (импорт контакта) и отправить сообщение.
    Возвращает None при успехе, иначе строку ошибки.
    """
    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return "Неверный формат телефона"
    try:
        result = await client(
            functions.contacts.ImportContactsRequest(
                contacts=[
                    types.InputPhoneContact(
                        client_id=random.randrange(0, 2**63),
                        phone=phone_norm,
                        first_name="",
                        last_name="",
                    )
                ]
            )
        )
        if not result.imported:
            return "Номер не зарегистрирован в Telegram или недоступен"
        user_id = result.imported[0].user_id
        await client.send_message(user_id, text)
        return None
    except Exception as e:
        return str(e)


async def _process_sheet() -> None:
    if not config.GOOGLE_SPREADSHEET_ID:
        logger.error("GOOGLE_SPREADSHEET_ID не задан.")
        return
    path = getattr(config, "GOOGLE_CREDENTIALS_PATH", None) or (config.PROJECT_ROOT / "google_credentials.json")
    if isinstance(path, str):
        path = Path(path)
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    if not path.exists():
        logger.error("Файл учётных данных Google не найден: %s", path)
        return

    gc = _get_client()
    sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
    try:
        worksheet = sh.worksheet(config.GOOGLE_SHEET_NAME)
    except Exception as e:
        logger.error("Лист «%s» не найден: %s", config.GOOGLE_SHEET_NAME, e)
        return

    rows = worksheet.get_all_values()
    if len(rows) <= 1:
        logger.info("В таблице нет данных (только заголовок).")
        return

    # Строки для отправки: индекс в rows (0 = заголовок), номер строки в листе (2-based)
    to_send: list[tuple[int, int]] = []
    for i in range(1, len(rows)):
        row = rows[i]
        send_cell = (row[7] if len(row) > 7 else "").strip().lower()
        if send_cell in ("1", "да", "отправить", "yes", "true"):
            to_send.append((i, i + 2))  # row index in sheet = i+2 (1-based + header)

    if not to_send:
        logger.info("Нет строк с «Отправить» = 1 или «да». Поставьте в колонке H значение 1 для нужных строк.")
        return

    logger.info("Найдено строк для отправки: %d. Подключаюсь к Telegram...", len(to_send))

    client = TelegramClient(
        str(config.SESSION_NAME),
        config.API_ID,
        config.API_HASH,
    )
    await client.start()
    me = await client.get_me()
    if getattr(me, "bot", False):
        logger.error("Для отправки в личку нужна сессия пользователя (по номеру), не бот.")
        return
    logger.info("Сессия: %s", getattr(me, "username", me.first_name))

    # Чтобы не писать одному и тому же контакту несколько раз за один запуск
    phones_sent: set[str] = set()
    users_sent: set[str] = set()
    status_updates: list[tuple[str, str]] = []  # (ячейка, статус)

    for row_idx, sheet_row_num in to_send:
        row = rows[row_idx]
        plate = (row[0] if len(row) > 0 else "").strip()
        sender = (row[3] if len(row) > 3 else "").strip()
        message_cell = (row[6] if len(row) > 6 else "").strip()
        phone = (row[8] if len(row) > 8 else "").strip()

        message_text = message_cell if message_cell else (get_client_message(plate) if plate else "")

        if not message_text:
            status = "Нет текста сообщения"
            logger.warning("Строка %s: %s", sheet_row_num, status)
        else:
            # 1. Пытаемся писать по нику, если он есть и это не канал-перекуп
            sent = False
            if sender:
                username = _normalize_sender(sender)
                username_l = username.lower()
                if username in IGNORED_SENDER_USERNAMES:
                    logger.warning(
                        "Строка %s: отправитель %s помечен как канал, по нику не пишу, пробую телефон (если есть).",
                        sheet_row_num,
                        username,
                    )
                elif username_l in users_sent:
                    status = f"Пропущено: уже писали @{username_l} в этом запуске"
                    logger.info(
                        "Строка %s: не отправляю, уже писали пользователю %s ранее.",
                        sheet_row_num,
                        username,
                    )
                    sent = True
                else:
                    err = await _send_by_username(client, username, message_text)
                    status = "Отправлено" if err is None else f"Ошибка: {err}"
                    if err:
                        logger.warning("Строка %s (@%s): %s", sheet_row_num, username, err)
                    else:
                        users_sent.add(username_l)
                        logger.info("Строка %s: отправлено @%s", sheet_row_num, username)
                        sent = True

            # 2. Если по нику не получилось или его нет — пробуем телефон
            if not sent and phone:
                phone_norm = normalize_phone(phone)
                if not phone_norm:
                    status = "Неверный формат телефона"
                    logger.warning("Строка %s (телефон): %s", sheet_row_num, status)
                elif phone_norm in phones_sent:
                    status = f"Пропущено: уже писали на {phone_norm} в этом запуске"
                    logger.info(
                        "Строка %s: не отправляю, номер %s уже использован ранее.",
                        sheet_row_num,
                        phone_norm,
                    )
                else:
                    err = await _send_by_phone(client, phone, message_text)
                    status = "Отправлено" if err is None else f"Ошибка: {err}"
                    if err:
                        logger.warning("Строка %s (телефон): %s", sheet_row_num, err)
                    else:
                        phones_sent.add(phone_norm)
                        logger.info("Строка %s: отправлено по номеру %s", sheet_row_num, phone_norm)
                    sent = True

            # 3. Если ни по нику, ни по телефону не получилось
            if not sent and not phone and sender and _normalize_sender(sender) in IGNORED_SENDER_USERNAMES:
                status = "Нет получателя (канал-источник, укажите Телефон или контакт из текста)"
                logger.warning("Строка %s: только канал-источник, контакта для связи нет.", sheet_row_num)
            elif not sent:
                status = "Нет получателя (укажите Отправитель или Телефон)"
                logger.warning("Строка %s: %s", sheet_row_num, status)
            else:
                # sent уже True, статус установлен при отправке выше
                pass

        status_updates.append((f"H{sheet_row_num}", status))

    # Обновляем колонку H батчами, чтобы не ловить лимит 429
    try:
        batch_size = 200
        for i in range(0, len(status_updates), batch_size):
            chunk = status_updates[i : i + batch_size]
            data = [
                {"range": cell, "values": [[status]]}
                for (cell, status) in chunk
            ]
            worksheet.batch_update(data, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.exception("Не удалось обновить статусы в колонке H батчем: %s", e)

    await client.disconnect()
    logger.info("Готово.")


def main() -> None:
    asyncio.run(_process_sheet())


if __name__ == "__main__":
    main()
