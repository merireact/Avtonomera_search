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
# Add channel usernames (e.g. "channelname") or numeric IDs (e.g. -1001234567890)
CHANNELS_TO_MONITOR: list[str] = [
    # Example: "autosale_channel",
    # -1001234567890,
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

# How many last messages to scan per channel on startup (0 = only new messages)
SCAN_LAST_MESSAGES = int(get_env("SCAN_LAST_MESSAGES") or "50")
