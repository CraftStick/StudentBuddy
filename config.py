# -*- coding: utf-8 -*-
"""Константы и настройки бота."""

import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

# Загрузка переменных окружения (для db_admin, health_check и др.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass(frozen=True)
class Settings:
    """
    Глобальные настройки бота, собранные из переменных окружения.
    Удобно использовать как единый объект конфигурации.
    """

    # Пути и токены из окружения (без значений по умолчанию для секретов)
    bot_token: str | None = os.getenv("BOT_TOKEN")
    schedule_api_token: str | None = os.getenv("SCHEDULE_API_TOKEN")
    database_path: str = os.getenv("DATABASE_PATH", "studentbuddy.db")
    persistence_file: str = os.getenv("PERSISTENCE_FILE", "data/studentbuddy_data.pickle")

    # Лимиты Telegram HTTP-клиента
    telegram_connect_timeout: float = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "30.0"))
    telegram_read_timeout: float = float(os.getenv("TELEGRAM_READ_TIMEOUT", "30.0"))

    # Поведение запуска/ретраев
    max_start_retries: int = int(os.getenv("MAX_START_RETRIES", "3"))
    start_retry_delay_sec: int = int(os.getenv("START_RETRY_DELAY_SEC", "10"))

    # Напоминания о занятиях
    reminder_default_offset_min: int = int(os.getenv("REMINDER_DEFAULT_OFFSET_MIN", "10"))
    reminder_window_min: int = int(os.getenv("REMINDER_WINDOW_MIN", "2"))
    reminder_job_interval_sec: int = int(os.getenv("REMINDER_JOB_INTERVAL_SEC", "60"))
    reminder_job_first_delay_sec: int = int(os.getenv("REMINDER_JOB_FIRST_DELAY_SEC", "15"))


settings = Settings()

# Краткие алиасы для часто используемых настроек (для удобства импорта)
BOT_TOKEN = settings.bot_token
SCHEDULE_API_TOKEN = settings.schedule_api_token
DATABASE_PATH = settings.database_path
PERSISTENCE_FILE = settings.persistence_file

# Часовой пояс расписания (API отдаёт время в московском времени)
SCHEDULE_TIMEZONE = ZoneInfo("Europe/Moscow")

# Состояния диалога: сначала корпус, затем группа (имя из Telegram)
BUILDING, GROUP = range(2)

# Формат группы: число + буквы + "-" + число + "-" + число (например 1ИП-3-25)
GROUP_PATTERN = re.compile(r"^\d+[А-Яа-яA-Za-z]+-\d+-\d+$", re.UNICODE)

# Ограничения длины пользовательского ввода
MAX_GROUP_LENGTH = 30
MAX_BUILDING_LENGTH = 100

# Список корпусов для выбора (фиксированный)
BUILDINGS_LIST = [
    "Судостроительная",
    "Коломенская",
    "Академика Миллионщикова",
    "Бирюлёво",
]

NOTIFICATIONS_ENABLED_KEY = "notifications_enabled"
LAST_REMINDER_KEY = "last_lesson_reminder"
LAST_REMINDER_MESSAGE_ID_KEY = "last_reminder_message_id"

# Транспорт: ключ состояния (очищается при /start)
TRANSPORT_STEP_KEY = "transport_step"

# Алиасы дней недели для команды /schedule
DAY_ALIASES = {
    "пн": 0, "пон": 0, "понедельник": 0,
    "вт": 1, "втор": 1, "вторник": 1,
    "ср": 2, "сред": 2, "среда": 2,
    "чт": 3, "чет": 3, "четверг": 3,
    "пт": 4, "пят": 4, "пятница": 4,
    "сб": 5, "суб": 5, "суббота": 5,
}

# Эмодзи для номеров пар (1️⃣ … 9️⃣)
NUMBER_EMOJI = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣")

# Лимит длины сообщения Telegram (символов)
MAX_MESSAGE_LENGTH = 4000

# Таймаут HTTP-запросов к API расписания (секунды)
SCHEDULE_API_TIMEOUT = 30.0
REPLACEMENTS_API_TIMEOUT = 15.0

# TTL кэша расписания (request coalescing), секунды (по умолчанию 10 минут)
SCHEDULE_CACHE_TTL = int(os.getenv("SCHEDULE_CACHE_TTL", "600"))

# Redis для кэша расписания (опционально). Если не задан — кэш в памяти (подходит для локалки).
# Пример: redis://localhost:6379/0  или  rediss://user:pass@host:6379/0
REDIS_URL = os.getenv("REDIS_URL")

# Эмодзи для предметов по ключевым словам (нижний регистр)
SUBJECT_EMOJI = {
    "математика": "📐",
    "химия": "🧪",
    "практика": "💻",
    "цифровой куратор": "💻",
    "цифровая грамотность": "💻",
    "проектный менеджмент": "📊",
    "информатика": "🖥",
    "физика": "⚛️",
    "русский": "📝",
    "литература": "📚",
    "история": "📜",
    "физкультура": "🏃",
    "английский": "🌐",
    "обж": "🛡️",
}

# Глобальный coalescer для API расписания (схлопывание запросов)
# С Redis (REDIS_URL) кэш общий для воркеров; без — в памяти (удобно на локалке)
from utils.request_coalescer import RequestCoalescer

_schedule_cache_backend = None
if REDIS_URL:
    from utils.redis_cache import RedisScheduleBackend

    _schedule_cache_backend = RedisScheduleBackend(REDIS_URL)

schedule_coalescer = RequestCoalescer(ttl=SCHEDULE_CACHE_TTL, backend=_schedule_cache_backend)

# Разрешённые значения интервала напоминаний (в минутах)
REMINDER_INTERVAL_OPTIONS: tuple[int, ...] = (5, 10, 15, 30)

# Алиасы для настроек напоминаний (mins/window), чтобы не тянуть весь Settings
REMINDER_DEFAULT_OFFSET_MIN = settings.reminder_default_offset_min
REMINDER_WINDOW_MIN = settings.reminder_window_min

# Алиасы для настроек задач JobQueue
REMINDER_JOB_INTERVAL_SEC = settings.reminder_job_interval_sec
REMINDER_JOB_FIRST_DELAY_SEC = settings.reminder_job_first_delay_sec

# Алиасы для настроек запуска/ретраев Telegram-пула
MAX_START_RETRIES = settings.max_start_retries
START_RETRY_DELAY_SEC = settings.start_retry_delay_sec

# Алиасы для таймаутов Telegram HTTP-клиента
TELEGRAM_CONNECT_TIMEOUT = settings.telegram_connect_timeout
TELEGRAM_READ_TIMEOUT = settings.telegram_read_timeout
