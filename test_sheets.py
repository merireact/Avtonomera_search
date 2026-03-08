#!/usr/bin/env python3
"""
Проверка доступа к Google Таблице. Запустите: python test_sheets.py
Покажет точную ошибку, если что-то не так.
"""
import sys
from pathlib import Path

# убедимся, что подхватывается .env и конфиг
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config

def main():
    print("ID таблицы:", config.GOOGLE_SPREADSHEET_ID)
    print("Файл ключа:", config.GOOGLE_CREDENTIALS_PATH)
    path = Path(config.GOOGLE_CREDENTIALS_PATH) if isinstance(config.GOOGLE_CREDENTIALS_PATH, str) else config.GOOGLE_CREDENTIALS_PATH
    print("Файл ключа существует:", path.exists())
    if not path.exists():
        print("\nОшибка: файл с ключом не найден. Положите google_credentials.json в папку проекта.")
        return

    print("\nПодключаюсь к Google и пробую записать одну строку...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as e:
        print("Ошибка: не установлены библиотеки. Выполните: pip install gspread google-auth")
        return

    try:
        creds = Credentials.from_service_account_file(
            str(path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        print("Клиент создан.")

        sh = gc.open_by_key(config.GOOGLE_SPREADSHEET_ID)
        print("Таблица открыта:", sh.title)

        # Пробуем первый лист (как в вашей ссылке gid=0)
        try:
            ws = sh.worksheet(config.GOOGLE_SHEET_NAME)
            print("Лист найден:", config.GOOGLE_SHEET_NAME)
        except Exception as e:
            print(f"Лист '{config.GOOGLE_SHEET_NAME}' не найден, создаю... Ошибка при поиске: {e}")
            ws = sh.add_worksheet(title=config.GOOGLE_SHEET_NAME, rows=1000, cols=10)
            print("Лист создан.")

        # Заголовок, если пусто
        if not ws.cell(1, 1).value:
            ws.append_row(["Номер", "Канал", "Ссылка", "Отправитель", "Дата", "Текст сообщения"], value_input_option="USER_ENTERED")
            print("Добавлена строка заголовков.")

        ws.append_row(
            ["[тест]", "проверка test_sheets.py", "", "", "", "Если видите это — доступ работает."],
            value_input_option="USER_ENTERED",
        )
        print("Строка с данными добавлена.")
        print(f"\nУспех. Данные записаны на лист «{config.GOOGLE_SHEET_NAME}».")
        print("Внизу таблицы нажмите на вкладку «Номера» — строка будет там (не на «Лист 1»).")
    except gspread.exceptions.APIError as e:
        print("\nОшибка API Google:")
        print(e)
        if "PERMISSION_DENIED" in str(e) or "403" in str(e):
            print("\n→ Скорее всего, таблица не расшарена с сервисным аккаунтом.")
            print("  Откройте таблицу → Поделиться → добавьте:")
            print("  python-sheets@autonomersheets.iam.gserviceaccount.com")
            print("  с правом «Редактор».")
    except Exception as e:
        print("\nОшибка:", type(e).__name__, e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
