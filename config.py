"""
Configuration module for the Telegram plate monitor.

Loads settings from environment variables (and optional .env file)
and defines channels/groups to monitor. Used for market analytics data collection.
"""

import os
from pathlib import Path

# Load .env file if present (optional; env vars still override)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass


def get_env(key: str, default: str | None = None) -> str | None:
    """
    Get environment variable value.
    Returns default if not set or empty.
    """
    value = os.environ.get(key, default)
    return value if value else default


# --- Telegram API credentials (from https://my.telegram.org) ---
API_ID = get_env("API_ID")
API_HASH = get_env("API_HASH")

# --- Bot token for sending notifications (from @BotFather) ---
BOT_TOKEN = get_env("BOT_TOKEN")

# --- Chat ID where the bot will send notifications (your user or group) ---
# Get it by messaging @userinfobot or your bot and checking updates
NOTIFICATION_CHAT_ID = get_env("NOTIFICATION_CHAT_ID")

# --- List of channel/group usernames or IDs to monitor ---
CHANNELS_TO_MONITOR: list[str] = [
    "vipavtonomer",
    "NomeraMsk77",
    "Avtorynok_moskva_24",
    "nomer_auto_77",
    "Avtonomerarus",
    "spec_nomera",
    "avto_nomer_rus",
    "grz_msk",
    "avtonomeraru",
    "autonomeraa777",
    "+Pl4V4GCOFV45MDIy",  # invite link t.me/+...
    "avtonomera777_77",
    "runomer",
    "GosNomeraRF",
    "regznak",
    "avtonomera_moskva",
    "+UMr3VKUxAE0yZWJi",
    "+Pl4V4GCOFV45MDIy",
    "Avtonomerarus",
    "snomerami",
]

def _normalize_channel(s: str) -> str:
    """Strip t.me/ prefix so we pass username or +invite_hash to Telethon."""
    s = s.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if s.startswith(prefix):
            return s[len(prefix) :].strip()
    return s


# Load from env if set (comma-separated): CHANNELS=channel1,channel2,-100123
_channels_env = get_env("CHANNELS")
if _channels_env:
    CHANNELS_TO_MONITOR.extend(
        _normalize_channel(s) for s in _channels_env.split(",") if s.strip()
    )


# --- Paths ---
# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent

# SQLite database file path
DATABASE_PATH = PROJECT_ROOT / "plates.db"

# CSV output file path (append mode)
CSV_PATH = PROJECT_ROOT / "plates.csv"

# Session file for Telethon (keeps login state)
SESSION_NAME = PROJECT_ROOT / "telegram_session"

# --- Google Sheets (optional) ---
# Path to service account JSON key file, or leave empty to disable
GOOGLE_CREDENTIALS_PATH = get_env("GOOGLE_CREDENTIALS_PATH") or (PROJECT_ROOT / "google_credentials.json")
# Spreadsheet ID from URL: https://docs.google.com/spreadsheets/d/THIS_PART/edit
GOOGLE_SPREADSHEET_ID = get_env("GOOGLE_SPREADSHEET_ID")
# Sheet (tab) name inside the spreadsheet, default first sheet
GOOGLE_SHEET_NAME = get_env("GOOGLE_SHEET_NAME") or "Номера"

# How many last messages to scan per channel on startup (0 = only new messages).
# Больше значение — больше старых номеров попадёт в таблицу (удобно ночью, когда новых постов мало).
SCAN_LAST_MESSAGES = int(get_env("SCAN_LAST_MESSAGES") or "200")
# По сколько сообщений брать с каждого канала за один «круг» (чтобы номера шли вперемешку: 5 с канала 1, 5 с канала 2, ...)
SCAN_BATCH_PER_CHANNEL = int(get_env("SCAN_BATCH_PER_CHANNEL") or "5")

# --- Фильтрация перекупов ---
# Сообщения длиннее этого символа не используем (длинные списки с ценами — перекупы)
MAX_MESSAGE_LENGTH_FOR_PLATES = int(get_env("MAX_MESSAGE_LENGTH_FOR_PLATES") or "350")

# Аккаунты перекупов (чёрный список): номера из их сообщений не добавляем в таблицу
BLOCKED_SENDERS: list[str] = [
    "autonomera777rus",
    "AUTOMOBILE_77",
    "Avtonomer55555",
    "rusnumberadmin",
    "Nidm77",
    "nomer77rus",
    "todor77",
    "zmeyhunter77",
    "ildar_r_k",
    "ExclusivepriceMSK",
    "nomera_avto99",
    "firmap",
    "ironchik15",
    "rozarenov",
    "Avtonoomerolog",
    "vipavtonomer",
    "autonomeraa777",
    "krllzvlv",
    "PrimeAvtonomer",
    "Avtonomera500",
    "Cardealers_77",
    "autoyurist",
    "Phantomi85",
    "zverev023",
    "Ruslan_lev77",
    "aleksei_minakov",
    # Дополнительно добавленные перекупы
    "zverev023",
    "Avtonoomerolog",
    "avtonomeramarket",
    "Vasilii_Fomkin",
    "pavlov_prod",
    "LuckyDo1",
]

# --- Фильтр по региону: только Москва и Московская область ---
# Коды региона в конце номера (2–3 цифры). Номера с другими регионами не добавляем и не ищем.
# Москва
MOSCOW_REGION_CODES: tuple[str, ...] = (
    "77", "97", "99", "177", "197", "199", "777", "797", "799", "977",
)
# Московская область
MOSCOW_OBLAST_REGION_CODES: tuple[str, ...] = (
    "50", "90", "150", "190", "750", "790", "250", "550",
)
# Все разрешённые коды (Москва + МО) — для быстрой проверки
ALLOWED_REGION_CODES: frozenset[str] = frozenset(MOSCOW_REGION_CODES) | frozenset(MOSCOW_OBLAST_REGION_CODES)

# Номера из списков перекупов — удалить из таблицы и не добавлять (нормализованы: без пробелов, верхний регистр)
BLOCKED_PLATES: set[str] = {
    "С869ЕР977", "В796РС797", "С763ЕР977", "С852ЕР977", "Е443КР977", "Е392КР977",
    "Е637КР977", "Е121АО797", "А771СА797", "Е704КР977", "Н367ОО797", "В434СЕ797",
    "К343ХХ797", "Х345УС797", "Т051ЕН977", "Т042ЕН977", "У191КУ977", "У474СН797",
    "Т075ЕН977", "Т171РЕ797", "Е022УО797", "Т959УВ797", "Н454РТ797", "С780ЕР977",
    "С980ЕР977", "Т191ХУ797", "У606ХН797", "А079МВ977", "К101ХВ797", "М765АХ977",
    "М202ТА799", "Р471УС197", "Е667КР977", "А090ТК",
}
