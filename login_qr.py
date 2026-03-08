#!/usr/bin/env python3
"""
Вход по QR-коду (без кода в чат).
Запустите: python login_qr.py
Отсканируйте QR-код в Telegram (Настройки → Устройства → Подключить рабочий стол).
Сессия сохранится, затем запускайте python main.py — код вводить не нужно.
"""
import asyncio
import urllib.parse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
from telethon import TelegramClient


async def main():
    if not config.API_ID or not config.API_HASH:
        print("Укажите API_ID и API_HASH в .env")
        return

    session_file = Path(f"{config.SESSION_NAME}.session")
    if session_file.exists():
        print("Внимание: уже есть файл сессии. Если раньше входили как бот — удалите файлы:")
        print("  rm -f telegram_session.session telegram_session.session-journal")
        print("и снова запустите: python login_qr.py\n")

    client = TelegramClient(
        str(config.SESSION_NAME),
        config.API_ID,
        config.API_HASH,
    )

    await client.connect()
    if not await client.is_user_authorized():
        print("Вход по QR-коду (код в чат не приходит).\n")
        qr = await client.qr_login()
        url = qr.url
        qr_link = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + urllib.parse.quote(url)
        print("1. Откройте эту ссылку в браузере (появится QR-код):")
        print(qr_link)
        print("\n2. В Telegram на телефоне: Настройки → Устройства → Подключить рабочий стол")
        print("3. Отсканируйте QR-код с экрана.\n")
        try:
            await qr.wait(timeout=120)
            print("Вход выполнен. Сессия сохранена. Теперь можно запускать: python main.py")
        except Exception as e:
            if "timeout" in str(e).lower() or "120" in str(e):
                print("Время вышло. Запустите скрипт снова и отсканируйте QR быстрее.")
            else:
                print("Ошибка:", e)
    else:
        print("Вы уже авторизованы. Запускайте: python main.py")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
