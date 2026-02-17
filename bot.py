# -*- coding: utf-8 -*-
"""
Бот расписания колледжа — приветствие, сбор имени и группы, показ расписания.
Точка входа: регистрация обработчиков и запуск приложения.
"""

import builtins
import os
import sys
import logging
import warnings

from dotenv import load_dotenv
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    PicklePersistence,
)

from config import BUILDING, GROUP
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
)

load_dotenv()

warnings.filterwarnings(
    "ignore",
    message=".*per_.*settings.*",
    category=builtins.UserWarning,
)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Задай BOT_TOKEN в .env (скопируй из .env.example)")
        return
    
    # Инициализируем базу данных
    db = Database()
    logger.info("База данных SQLite инициализирована")
    
    persistence_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studentbuddy_data.pickle")
    persistence = PicklePersistence(filepath=persistence_file)
    app = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .get_updates_read_timeout(30)
        .get_updates_connect_timeout(10)
        .job_queue()
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
    app.add_handler(MessageHandler(filters.Regex("^❌ Отмена$"), cancel_or_ok))
    # Специфичные хендлеры регистрируем ПЕРЕД общими!
    app.add_handler(CallbackQueryHandler(settings_menu, pattern=r"^main:settings$"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(back_to_settings, pattern=r"^back:settings$"))
    app.add_handler(CallbackQueryHandler(schedule_by_day_callback, pattern=r"^sched:"))
    # Общие хендлеры в конце
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern=r"^main:"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern=r"^back:"))

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(send_lesson_reminders, interval=60, first=15)
        logger.info("Включены уведомления за 10 минут до урока")
    else:
        logger.warning("JobQueue недоступен — уведомления за 10 мин до урока отключены")

    logger.info("Бот запущен")

    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except (NetworkError, TimedOut) as e:
        logger.error(
            "Не удалось подключиться к Telegram.\n"
            "Проверь:\n"
            "  • Есть ли интернет (Wi‑Fi или мобильные данные)\n"
            "  • Правильный ли BOT_TOKEN в .env\n"
            "  • Не блокирует ли Telegram файрвол или VPN\n"
            "Ошибка: %s",
            e,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
