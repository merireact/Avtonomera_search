"""
Entry point for the Telegram plate monitor.

Runs the monitor continuously, watching configured channels/groups
for Russian car license plates and saving results to SQLite and CSV.
"""

import asyncio
import logging
import sys

from telegram_monitor import run_monitor

# Configure logging to stdout so the user sees activity
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)


def main() -> None:
    """Start the Telegram monitor and run until interrupted."""
    try:
        asyncio.run(run_monitor())
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    except Exception as e:
        logging.exception("Monitor failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
