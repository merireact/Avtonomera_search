"""
Telegram monitor module using Telethon.

Connects to Telegram, listens to configured channels/groups,
extracts Russian plate numbers from new messages, stores them,
and sends a notification via bot when a new plate is found.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telethon import TelegramClient
from telethon.events import NewMessage
import config
from database import append_to_csv, init_database, insert_plate
from plate_detector import find_plates
from sheets import append_plate_row

# Set up logging for the monitor
logger = logging.getLogger("telegram_monitor")


def _get_message_text(msg) -> str:
    """Extract plain text from a message (text + caption for media)."""
    text = getattr(msg, "text", None) or getattr(msg, "message", None) or ""
    if not text and getattr(msg, "photo", None) is not None:
        text = getattr(msg, "raw_text", None) or msg.message or ""
    return text or ""


def _get_sender_username(sender) -> Optional[str]:
    """Get username of the message sender if available."""
    if sender is None:
        return None
    if hasattr(sender, "username") and sender.username:
        return f"@{sender.username}"
    if hasattr(sender, "title"):  # e.g. Channel/Chat as sender
        return getattr(sender, "title", None)
    return None


def _get_channel_name(chat) -> str:
    """Get display name of the channel or group."""
    if chat is None:
        return "unknown"
    if hasattr(chat, "title"):
        return chat.title or "unknown"
    return "unknown"


def _build_message_link(chat, msg_id: int) -> str:
    """Build a t.me link to the message. Uses username for public channels."""
    if hasattr(chat, "username") and getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{msg_id}"
    chat_id = getattr(chat, "id", 0) or 0
    # Private supergroups: t.me/c/<id_without_-100>/<msg_id>
    id_part = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{id_part}/{msg_id}"


async def _send_notification(plate: str, channel: str, message_link: str) -> None:
    """
    Send a Telegram notification to the configured chat via the bot.
    """
    if not config.BOT_TOKEN or not config.NOTIFICATION_CHAT_ID:
        logger.warning("BOT_TOKEN or NOTIFICATION_CHAT_ID not set; skipping notification.")
        return

    try:
        # Use a separate client for the bot (only for sending)
        bot = TelegramClient(
            "bot_session",
            config.API_ID,
            config.API_HASH,
        )
        await bot.start(bot_token=config.BOT_TOKEN)

        text = (
            "New plate found\n"
            f"Plate: {plate}\n"
            f"Channel: {channel}\n"
            f"Link: {message_link}"
        )
        chat_id = config.NOTIFICATION_CHAT_ID
        # Support both numeric ID and @username
        if chat_id.lstrip("-").isdigit():
            chat_id = int(chat_id)
        await bot.send_message(chat_id, text)
        await bot.disconnect()
    except Exception as e:
        logger.exception("Failed to send Telegram notification: %s", e)


async def _send_startup_test() -> None:
    """
    Send a test message to the bot and append a test row to Google Sheet.
    So you can verify NOTIFICATION_CHAT_ID and Sheets access right after start.
    """
    if config.BOT_TOKEN and config.NOTIFICATION_CHAT_ID:
        try:
            bot = TelegramClient(
                "bot_startup_test",
                config.API_ID,
                config.API_HASH,
            )
            await bot.start(bot_token=config.BOT_TOKEN)
            chat_id = config.NOTIFICATION_CHAT_ID
            if chat_id.lstrip("-").isdigit():
                chat_id = int(chat_id)
            await bot.send_message(
                chat_id,
                "Монитор запущен. Ожидаю новые сообщения в каналах. Когда в канале появится сообщение с номером — пришлю уведомление сюда.",
            )
            await bot.disconnect()
            logger.info("Startup test: message sent to bot (check your Telegram).")
        except Exception as e:
            logger.error(
                "Startup test: could not send message to bot. Check NOTIFICATION_CHAT_ID (must be YOUR chat ID, not bot ID) and that you have sent /start to the bot. Error: %s",
                e,
            )
    else:
        logger.warning("BOT_TOKEN or NOTIFICATION_CHAT_ID not set; bot notifications disabled.")

    if config.GOOGLE_SPREADSHEET_ID:
        from sheets import append_plate_row
        test_row = {
            "plate": "[тест]",
            "source_channel": "проверка при запуске",
            "message_link": "",
            "sender": "",
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Если видите эту строку — доступ к таблице работает.",
        }
        if append_plate_row(test_row):
            logger.info("Startup test: test row added to Google Sheet.")
        else:
            logger.warning(
                "Startup test: could not add row to Sheet. Check that the sheet is shared with the service account email from google_credentials.json (Editor) and GOOGLE_SPREADSHEET_ID is correct.",
            )
    else:
        logger.info("GOOGLE_SPREADSHEET_ID not set; Google Sheets disabled.")


def _process_message(
    msg,
    chat,
    channel_name: str,
    message_link: str,
    date_str: str,
    sender_username: Optional[str],
) -> None:
    """
    Process one message: find plates, avoid duplicates, save to DB/CSV,
    and send notification for each newly stored plate.
    """
    text = _get_message_text(msg)
    plates = find_plates(text)

    for plate in plates:
        inserted = insert_plate(
            plate=plate,
            source_channel=channel_name,
            sender=sender_username,
            message=text,
            message_link=message_link,
            date=date_str,
        )
        if inserted:
            row = {
                "plate": plate,
                "source_channel": channel_name,
                "sender": sender_username or "",
                "message": text,
                "message_link": message_link,
                "date": date_str,
            }
            append_to_csv(row)
            append_plate_row(row)
            # Notify asynchronously without blocking the handler
            asyncio.create_task(
                _send_notification(plate, channel_name, message_link)
            )


async def _handle_new_message(event: NewMessage.Event) -> None:
    """Telethon handler for new messages in monitored chats."""
    msg = event.message
    chat = await event.get_chat()
    channel_name = _get_channel_name(chat)
    sender = await msg.get_sender()
    sender_username = _get_sender_username(sender)

    # Message link: use channel username if public, else chat id
    message_link = _build_message_link(chat, msg.id)

    # Date in ISO format for storage
    date_obj = msg.date
    if date_obj:
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    text_preview = (_get_message_text(msg) or "")[:80].replace("\n", " ")
    plates = find_plates(_get_message_text(msg))
    logger.info("Новое сообщение в «%s»: «%s...» — найдено номеров: %d", channel_name, text_preview, len(plates))

    _process_message(
        msg,
        chat,
        channel_name,
        message_link,
        date_str,
        sender_username,
    )


async def _process_one_message(
    client: TelegramClient,
    msg,
    chat,
    channel_name: str,
    message_link: str,
    date_str: str,
    sender_username: Optional[str],
) -> None:
    """Process a single message (used both for new messages and for startup scan)."""
    _process_message(
        msg,
        chat,
        channel_name,
        message_link,
        date_str,
        sender_username,
    )


async def _scan_recent_messages(client: TelegramClient, channels_resolved: list) -> None:
    """Fetch last N messages from each channel and process them (find plates, save, notify)."""
    limit = getattr(config, "SCAN_LAST_MESSAGES", 50) or 0
    if limit <= 0:
        return

    if not channels_resolved:
        return

    logger.info("Сканирую последние %d сообщений в каждом канале...", limit)
    for entity in channels_resolved:
        try:
            channel_name = getattr(entity, "title", None) or "unknown"
            messages = await client.get_messages(entity, limit=limit)
            for msg in messages:
                if not msg or not msg.id:
                    continue
                message_link = _build_message_link(entity, msg.id)
                date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""
                sender = await msg.get_sender()
                sender_username = _get_sender_username(sender)
                text = _get_message_text(msg)
                plates = find_plates(text)
                if plates:
                    logger.info("В истории «%s»: найдено номеров %d в сообщении %s", channel_name, len(plates), msg.id)
                await _process_one_message(
                    client,
                    msg,
                    entity,
                    channel_name,
                    message_link,
                    date_str,
                    sender_username,
                )
        except Exception as e:
            logger.warning("Ошибка при сканировании канала %s: %s", getattr(entity, "title", entity), e)
    logger.info("Сканирование истории завершено. Ожидаю новые сообщения...")


async def run_monitor() -> None:
    """
    Initialize DB, create Telethon client, resolve channels, add handlers,
    optionally scan recent messages, then run until disconnected.
    """
    if not config.API_ID or not config.API_HASH:
        raise ValueError("API_ID and API_HASH must be set in environment")

    if not config.CHANNELS_TO_MONITOR:
        logger.warning("CHANNELS_TO_MONITOR is empty; add channel usernames or IDs.")

    init_database()

    client = TelegramClient(
        str(config.SESSION_NAME),
        config.API_ID,
        config.API_HASH,
    )

    await client.start()
    me = await client.get_me()
    if getattr(me, "bot", False):
        logger.error(
            "Текущая сессия — это бот. Для мониторинга каналов и чтения истории нужен вход как пользователь (по номеру телефона). "
            "Удалите в папке проекта файлы: telegram_session.session и telegram_session.session-journal (если есть), "
            "затем запустите скрипт снова — введите номер телефона и код из Telegram."
        )
        raise SystemExit(1)
    logger.info("Telegram monitor started (пользователь: %s).", getattr(me, "first_name", "?"))

    # Resolve channel identifiers to entities (so invite links and usernames work)
    resolved = []
    for ch in config.CHANNELS_TO_MONITOR:
        try:
            # Try as-is, then with t.me/ prefix for invite links
            ent = await client.get_entity(ch)
            resolved.append(ent)
            logger.info("Канал подключён: %s", getattr(ent, "title", ch))
        except Exception as e:
            try:
                ent = await client.get_entity(f"https://t.me/{ch}" if not ch.startswith("http") else ch)
                resolved.append(ent)
                logger.info("Канал подключён (по ссылке): %s", getattr(ent, "title", ch))
            except Exception as e2:
                logger.warning("Не удалось подключить канал «%s»: %s", ch, e2)
    if not resolved:
        logger.warning("Ни один канал не подключён. Проверьте CHANNELS и что вы вступили в каналы/группы.")

    # Register handler for new messages
    for entity in resolved:
        client.add_event_handler(
            _handle_new_message,
            NewMessage(chats=[entity]),
        )

    await _send_startup_test()

    # Scan last N messages in each channel so we find plates from recent posts
    await _scan_recent_messages(client, resolved)

    # Run until disconnected
    await client.run_until_disconnected()
