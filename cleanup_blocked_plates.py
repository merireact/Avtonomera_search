"""
Скрипт очистки таблицы от перекупов и «мусорных» строк.

1) Удаляет записи с номерами из config.BLOCKED_PLATES.
2) Удаляет записи с номерами, у которых регион не Москва и не Московская область.
3) Удаляет записи, где отправитель — перекуп (BLOCKED_SENDERS).
4) Удаляет записи, где текст сообщения слишком длинный (списки с ценами).
5) Удаляет записи, где текст в формате списка перекупов (номера-цены, «СПИСОК», «ЦЕНА БЕЗ ОФОРМЛЕНИЯ»).

Запуск: python cleanup_blocked_plates.py
"""

import logging
import sys

import config
from database import delete_by_ids, delete_plates, get_all_rows, init_database
from filters import is_blocked_sender, is_reseller_list_message, is_message_too_long
from plate_detector import get_region_code
from sheets import delete_reseller_and_long_message_rows, delete_rows_with_plates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("cleanup")


def _should_remove_row(row: dict) -> bool:
    """Удалить строку, если перекуп, длинное сообщение или список с ценами."""
    sender = (row.get("sender") or "").strip()
    message = (row.get("message") or "").strip()
    return (
        is_blocked_sender(sender)
        or is_message_too_long(message)
        or is_reseller_list_message(message)
    )


def main() -> None:
    init_database()

    # 1. Удаление по чёрному списку номеров
    if config.BLOCKED_PLATES:
        logger.info("Удаление номеров из BLOCKED_PLATES (%d шт.)...", len(config.BLOCKED_PLATES))
        deleted_db = delete_plates(config.BLOCKED_PLATES)
        logger.info("  БД: удалено записей %d", deleted_db)
        deleted_sheet = delete_rows_with_plates(config.BLOCKED_PLATES)
        logger.info("  Google Таблица: удалено строк %d", deleted_sheet)

    # 2. Удаление номеров с регионом не Москва и не Московская область
    rows = get_all_rows()
    plates_wrong_region = set()
    for r in rows:
        plate = (r.get("plate") or "").strip()
        if plate and get_region_code(plate) not in config.ALLOWED_REGION_CODES:
            plates_wrong_region.add(plate)
    if plates_wrong_region:
        logger.info("Удаление номеров с регионом не Москва/МО (%d шт.)...", len(plates_wrong_region))
        deleted_db = delete_plates(plates_wrong_region)
        logger.info("  БД: удалено записей %d", deleted_db)
        deleted_sheet = delete_rows_with_plates(plates_wrong_region)
        logger.info("  Google Таблица: удалено строк %d", deleted_sheet)
    else:
        logger.info("Номеров с регионом не Москва/МО не найдено.")

    # 3. Удаление строк от перекупов, длинных сообщений и списков с ценами
    logger.info("Удаление строк перекупов / длинных сообщений / списков с ценами...")
    rows = get_all_rows()  # перечитаем после удаления по региону
    ids_to_remove = [r["id"] for r in rows if _should_remove_row(r)]
    if ids_to_remove:
        deleted_db = delete_by_ids(ids_to_remove)
        logger.info("  БД: удалено записей %d", deleted_db)
    else:
        logger.info("  БД: нечего удалять")

    deleted_sheet = delete_reseller_and_long_message_rows(
        lambda row: _should_remove_row(row),
    )
    logger.info("  Google Таблица: удалено строк %d", deleted_sheet)

    logger.info("Готово.")


if __name__ == "__main__":
    main()
