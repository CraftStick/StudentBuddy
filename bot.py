# -*- coding: utf-8 -*-
"""
Бот расписания колледжа — приветствие, сбор имени и группы, показ расписания.
Точка входа: регистрация обработчиков и запуск приложения.
"""

import builtins
import os
import sys
import time
import logging
import warnings
import signal
from typing import Any

from dotenv import load_dotenv

# Загружаем .env до импортов (config, cache, rate limit)
load_dotenv()

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from telegram.request import HTTPXRequest

from config import (
    BUILDING,
    GROUP,
    DATABASE_PATH,
    PERSISTENCE_FILE,
    MAX_START_RETRIES,
    REMINDER_JOB_FIRST_DELAY_SEC,
    REMINDER_JOB_INTERVAL_SEC,
    START_RETRY_DELAY_SEC,
    TELEGRAM_CONNECT_TIMEOUT,
    TELEGRAM_READ_TIMEOUT,
)
from database import Database
from handlers import (
    start,
    back_to_building,
    receive_building_callback,
    receive_building,
    receive_group,
    cancel,
    cancel_or_ok,
    reply_finish_building,
    reply_finish_group,
    menu,
    main_menu_callback,
    back_callback,
    schedule_day_picker,
    schedule,
    schedule_by_day_callback,
    send_lesson_reminders,
    error_handler,
    settings_menu,
    settings_callback,
    language_callback,
    back_to_settings,
    notifications_submenu_callback,
    buses_menu,
    buses_direction_callback,
)

warnings.filterwarnings(
    "ignore",
    message=".*per_.*settings.*",
    category=builtins.UserWarning,
)


def configure_logging() -> logging.Logger:
    """Настройка логирования из переменных окружения."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if log_level == "DEBUG":
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        )

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format))
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))

    logging.basicConfig(
        format=log_format,
        level=getattr(logging, log_level, logging.INFO),
        handlers=[
            logging.StreamHandler(),
            file_handler,
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger(__name__)


logger = configure_logging()


def create_app(token: str) -> Application:
    """
    Создаёт и настраивает экземпляр Application:
    persistence, HTTP-клиент, хендлеры и фоновые задачи.
    """
    # Путь к файлу persistence (каталог data/ создаётся при необходимости)
    persistence_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), PERSISTENCE_FILE
    )
    os.makedirs(os.path.dirname(persistence_file), exist_ok=True)
    persistence = PicklePersistence(filepath=persistence_file)

    # Увеличенные таймауты для нестабильной сети — применяются ко всем запросам, включая get_updates
    request = HTTPXRequest(
        connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        read_timeout=TELEGRAM_READ_TIMEOUT,
    )
    app = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .request(request)
        .build()
    )

    app.add_error_handler(error_handler)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(settings_callback, pattern=r"^settings:"),
        ],
        states={
            BUILDING: [
                CallbackQueryHandler(receive_building_callback, pattern=r"^building:"),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.Regex("^📅 Расписание$"), reply_finish_building),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_building),
                CommandHandler("cancel", cancel),
            ],
            GROUP: [
                CallbackQueryHandler(back_to_building, pattern=r"^back:building$"),
                MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
                MessageHandler(filters.Regex("^📅 Расписание$"), reply_finish_group),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_group),
                CommandHandler("cancel", cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(MessageHandler(filters.Regex("^📅 Расписание$"), schedule_day_picker))
    app.add_handler(MessageHandler(filters.Regex(r"^🚌 "), buses_menu))
    app.add_handler(MessageHandler(filters.Regex("^❌ Отмена$"), cancel_or_ok))
    # Специфичные хендлеры регистрируем ПЕРЕД общими!
    app.add_handler(CallbackQueryHandler(settings_menu, pattern=r"^main:settings$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(back_to_settings, pattern=r"^back:settings$"))
    app.add_handler(CallbackQueryHandler(notifications_submenu_callback, pattern=r"^notif:"))
    app.add_handler(CallbackQueryHandler(schedule_by_day_callback, pattern=r"^sched:"))
    app.add_handler(CallbackQueryHandler(buses_direction_callback, pattern=r"^buses:"))
    # Общие хендлеры в конце
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^main:"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern=r"^back:"))

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(
            send_lesson_reminders,
            interval=REMINDER_JOB_INTERVAL_SEC,
            first=REMINDER_JOB_FIRST_DELAY_SEC,
        )
        logger.info("Включены уведомления перед уроком (job_queue активен)")
    else:
        logger.warning("JobQueue недоступен — уведомления перед уроком отключены")

    return app


def main() -> None:
    from config import BOT_TOKEN

    token = BOT_TOKEN
    if not token:
        logger.error("Задай BOT_TOKEN в .env (скопируй из .env.example)")
        return

    # Инициализируем базу данных (подтягивает схему, индексы и т.д.)
    db = Database(db_path=DATABASE_PATH)
    logger.info("База данных SQLite инициализирована: %s", DATABASE_PATH)

    app: Application = create_app(token)

    # Флаг для graceful shutdown
    shutdown_flag: dict[str, bool] = {"triggered": False}

    # Настройка graceful shutdown
    def signal_handler(signum: int, frame: Any | None) -> None:
        """Обработчик сигналов завершения (SIGINT, SIGTERM)."""
        if not shutdown_flag["triggered"]:
            shutdown_flag["triggered"] = True
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            logger.info("Получен сигнал %s, корректное завершение работы...", signal_name)
            # Останавливаем приложение
            app.stop_running()

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Бот запущен")

    for attempt in range(MAX_START_RETRIES):
        try:
            app.run_polling(allowed_updates=Update.ALL_TYPES)
            break
        except (NetworkError, TimedOut) as e:
            if attempt < MAX_START_RETRIES - 1:
                logger.warning(
                    "Таймаут/сеть при подключении к Telegram (попытка %s/%s), "
                    "повтор через %s сек: %s",
                    attempt + 1,
                    MAX_START_RETRIES,
                    START_RETRY_DELAY_SEC,
                    e,
                )
                time.sleep(START_RETRY_DELAY_SEC)
            else:
                logger.error(
                    "Не удалось подключиться к Telegram после %s попыток.\n"
                    "Проверь:\n"
                    "  • Есть ли интернет на сервере\n"
                    "  • Правильный ли BOT_TOKEN в .env\n"
                    "  • Не блокирует ли Telegram файрвол или VPN\n"
                    "Ошибка: %s",
                    MAX_START_RETRIES,
                    e,
                )
                sys.exit(1)


if __name__ == "__main__":
    main()
