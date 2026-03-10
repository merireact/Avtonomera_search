# Telegram Plate Monitor

Monitors Telegram channels and groups for Russian car license plate numbers and saves results to a SQLite database and CSV file. Sends a Telegram notification when a new plate is found. Designed for market analytics data collection.

## Requirements

- Python 3.11+
- Telegram API credentials (API_ID, API_HASH) from [my.telegram.org](https://my.telegram.org)
- Optional: a bot token from [@BotFather](https://t.me/BotFather) for notifications

## Setup

1. **Create a virtual environment (recommended):**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**  
   Copy `.env.example` to `.env` and set:
   - `API_ID` – Telegram API ID  
   - `API_HASH` – Telegram API hash  
   - `BOT_TOKEN` – Bot token (optional, for notifications)  
   - `NOTIFICATION_CHAT_ID` – Chat ID where the bot sends alerts  
   - `CHANNELS` – Comma-separated list of channel/group usernames or IDs to monitor  

   Alternatively set these in `config.py` (e.g. `CHANNELS_TO_MONITOR`) or export them in the shell.

4. **First run:**  
   When you run the script, Telethon will prompt you to log in (phone number, code). A session file will be created so you don’t need to log in again.

## Run

```bash
python main.py
```

The script runs continuously and processes new messages in real time. Stop with `Ctrl+C`.

## Output

- **SQLite:** `plates.db` – table `plates` with columns: `id`, `plate`, `source_channel`, `sender`, `message`, `message_link`, `date`. Duplicates (same plate + same message) are ignored.
- **CSV:** `plates.csv` – same fields, appended as new plates are found.
- **Google Sheets** (optional) – см. ниже.

## Google Таблицы

Чтобы найденные номера и ссылки на сообщения попадали в Google Таблицу:

1. **Google Cloud:** зайдите в [Google Cloud Console](https://console.cloud.google.com/) → создайте проект (или выберите существующий) → «APIs & Services» → «Enable APIs and Services» → включите **Google Sheets API**.

2. **Сервисный аккаунт:** «APIs & Services» → «Credentials» → «Create Credentials» → «Service account». Создайте аккаунт, откройте его → вкладка «Keys» → «Add key» → «Create new key» → JSON. Скачайте JSON-файл и положите в папку проекта как `google_credentials.json` (или укажите свой путь в `.env`).

3. **Таблица:** создайте новую Google Таблицу или откройте существующую. Скопируйте **ID таблицы** из URL:  
   `https://docs.google.com/spreadsheets/d/**ВОТ_ЭТОТ_ID**/edit`  
   Откройте доступ к таблице: «Поделиться» → добавьте email сервисного аккаунта из JSON (поле `client_email`, вид `xxx@xxx.iam.gserviceaccount.com`) с правом **Редактор**.

4. **Переменные в `.env`:**
   ```
   GOOGLE_SPREADSHEET_ID=ваш_id_таблицы
   GOOGLE_CREDENTIALS_PATH=google_credentials.json
   GOOGLE_SHEET_NAME=Номера
   ```
   Лист с именем «Номера» будет создаваться автоматически при первом добавлении строки, либо используйте первый лист (тогда можно не задавать `GOOGLE_SHEET_NAME` или задать имя вашего листа).

После запуска `python main.py` при каждом новом найденном номере в таблицу будет добавляться строка: **Номер**, **Канал**, **Ссылка**, **Отправитель**, **Дата**, **Текст сообщения**, **Сообщение для клиента**, **Отправить**, **Телефон**.

### Отправка сообщений клиентам из таблицы

В колонке **«Сообщение для клиента»** (G) подставляется номер; этот текст можно отправить в Telegram тому, кто написал в канале (по **Отправитель**, колонка D), либо по **Телефон** (колонка I), если отправителя нет.

1. В колонке **H «Отправить»** поставьте `1` или `да` для нужных строк.
2. При необходимости укажите **Телефон** (I) в формате +79... — тогда сообщение уйдёт по номеру (поиск в Telegram).
3. Запустите:
   ```bash
   python send_sheet_messages.py
   ```
   Скрипт отправит сообщения через вашу пользовательскую сессию Telegram и запишет в H результат («Отправлено» или ошибку).

Подробнее и скрипт для кнопки в таблице: [docs/SHEET_SEND_BUTTON.md](docs/SHEET_SEND_BUTTON.md).

## Project structure

```
main.py              # Entry point
telegram_monitor.py  # Telethon client, message handling, notifications
plate_detector.py    # Regex-based Russian plate detection
database.py          # SQLite and CSV storage
sheets.py            # Google Sheets append
send_sheet_messages.py  # Отправка сообщений из таблицы в Telegram (по username или телефону)
config.py            # Env vars and channel list
```

## Plate format

Распознаются варианты: с пробелами/дефисами (`А 123 ВС 77`, `А-123-СТ-77`), полный формат (`A777AA77`, `В123СТ77`), без буквы региона (`777АА77`, `123СТ77`). Буквы — латиница или кириллица.

---

## Почему не приходят уведомления в бота и ничего не пишется в таблицу

### Важно: обрабатываются только **новые** сообщения

Скрипт не читает старые сообщения в каналах. Он только слушает то, что приходит **после** запуска `python main.py`. Если в каналах после запуска не было новых сообщений с номерами — в бота и в таблицу ничего не попадёт.

### Telegram-бот: что проверить

1. **NOTIFICATION_CHAT_ID — это ваш личный Chat ID, не ID бота.**  
   Число `8714833254` — это первая часть токена бота (ID самого бота). Бот не может слать сообщения «себе». Нужен ID **вашего** аккаунта.

   **Как узнать свой Chat ID:**
   - Напишите в Telegram боту [@userinfobot](https://t.me/userinfobot) — он пришлёт ваш **Id** (например, `123456789`). Это и есть `NOTIFICATION_CHAT_ID`.
   - Либо напишите что-то своему боту (например, «привет»), затем откройте в браузере (подставьте свой токен):  
     `https://api.telegram.org/bot8ARWIxo/getUpdates`  
     В ответе найдите `"chat":{"id": 123456789}` — это ваш Chat ID.

   В `.env` пропишите:  
   `NOTIFICATION_CHAT_ID=ваш_настоящий_id`

2. **Вы должны хотя бы раз написать боту.**  
   Откройте бота в Telegram и отправьте команду `/start` или любое сообщение. Пока вы не начнёте диалог, бот не может инициировать переписку и отправить вам уведомление.

3. **Разрешения бота менять не нужно.**  
   Для отправки сообщений пользователю, который уже написал боту, дополнительных настроек в @BotFather не требуется.

При запуске скрипт отправляет в бота тестовое сообщение: *«Монитор запущен. Ожидаю новые сообщения...»*. Если это сообщение **не пришло** — проверьте пункты 1 и 2.

### Google Таблицы: что проверить

1. **Доступ к таблице.**  
   Таблица должна быть расшарена с email сервисного аккаунта из `google_credentials.json` (поле `client_email`, например `python-sheets@autonomersheets.iam.gserviceaccount.com`) с правом **Редактор** («Поделиться» → добавить пользователя).

2. **ID таблицы в `.env`.**  
   В переменной `GOOGLE_SPREADSHEET_ID` должен быть именно ID из URL:  
   `https://docs.google.com/spreadsheets/d/ВОТ_ЭТОТ_ID/edit`

3. **При запуске скрипт добавляет тестовую строку** в таблицу (номер `[тест]`, канал «проверка при запуске»). Если эта строка **не появилась** — в терминале будет предупреждение; проверьте доступ (п. 1) и ID таблицы (п. 2).
