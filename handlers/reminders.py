# -*- coding: utf-8 -*-
"""Напоминания за 10 минут до начала урока."""

import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError, TimedOut, NetworkError

from timetable import get_timetable
from config import (
    NOTIFICATIONS_ENABLED_KEY,
    LAST_REMINDER_KEY,
    LAST_REMINDER_MESSAGE_ID_KEY,
    SCHEDULE_TIMEZONE,
    DATABASE_PATH,
    REMINDER_DEFAULT_OFFSET_MIN,
    REMINDER_WINDOW_MIN,
)
from database import Database
from utils.user_helpers import get_user_language
from utils.time_utils import fix_saturday_time
from i18n import t

logger = logging.getLogger(__name__)
db = Database(db_path=DATABASE_PATH)

# Блокировка для защиты от race condition при отправке напоминаний.
# Очищаем замки пользователей, которые больше не в списке с уведомлениями.
_reminder_locks: dict[int, asyncio.Lock] = {}
_MAX_REMINDER_LOCKS = 5000

# Состояние напоминаний (last key, message_id) — в job нельзя писать в application.user_data (mappingproxy)
_reminder_state: dict[int, dict] = {}
_MAX_REMINDER_STATE = 5000


def _parse_time(s: str, today: datetime) -> datetime | None:
    """Парсит время из строки 'HH:MM' или 'H:MM'. Возвращает datetime сегодня в часовом поясе расписания."""
    s = (s or "").strip()
    if not s:
        return None
    parts = s.split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return today.replace(hour=h, minute=m, second=0, microsecond=0)
    except (ValueError, IndexError):
        return None


def _get_day_blocks(data: dict) -> list:
    """Возвращает список блоков дней из ответа API (поддержка списка и одного объекта)."""
    raw = data.get("data")
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "units" in raw:
        return [raw]
    return []


async def send_lesson_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Задача по расписанию: каждую минуту проверяем у всех пользователей с группой,
    есть ли следующий урок через ~10 минут. Если да — отправляем уведомление (один раз за урок).
    Время сравнивается в часовом поясе расписания (Europe/Moscow), чтобы корректно работало на сервере в UTC.
    """
    bot = context.bot
    application = context.application
    now = datetime.now(SCHEDULE_TIMEZONE)
    today_weekday = now.weekday()
    if today_weekday >= 6:
        logger.debug("Напоминания: воскресенье, пропуск")
        return

    today = now  # дата и время «сейчас» в поясе расписания (для парсинга времени урока)

    # Получаем всех пользователей с включенными уведомлениями из БД
    try:
        users = db.get_users_with_notifications()
    except Exception as e:
        logger.exception("Ошибка при получении пользователей из БД: %s", e)
        return

    logger.info(
        "Напоминания: проверка, время МСК %s, день недели %s, пользователей с уведомлениями %s",
        now.strftime("%H:%M"),
        today_weekday,
        len(users),
    )

    # Ограничиваем рост словаря блокировок: оставляем только замки для текущих user_id
    current_user_ids = {u.get("user_id") for u in users if u.get("user_id")}
    if len(_reminder_locks) > _MAX_REMINDER_LOCKS:
        to_remove = [uid for uid in _reminder_locks if uid not in current_user_ids]
        for uid in to_remove[:500]:  # Чистим порциями
            _reminder_locks.pop(uid, None)
        logger.debug("Очищено %s замков напоминаний", min(500, len(to_remove)))
    if len(_reminder_state) > _MAX_REMINDER_STATE:
        to_remove = [uid for uid in _reminder_state if uid not in current_user_ids]
        for uid in to_remove[:500]:
            _reminder_state.pop(uid, None)

    for user_db in users:
        user_id = user_db.get("user_id")
        if not user_id:
            continue
        
        # Получаем или создаём блокировку для пользователя
        if user_id not in _reminder_locks:
            _reminder_locks[user_id] = asyncio.Lock()
        
        try:
            # Используем блокировку для предотвращения race condition
            async with _reminder_locks[user_id]:
                group = user_db.get("student_group")
                if not group or not isinstance(group, str):
                    continue
                
                building = user_db.get("building")
                if not building:
                    logger.debug("Напоминания: у user_id=%s не указан корпус, пропуск", user_id)
                    continue

                # Интервал напоминаний для пользователя (в минутах)
                try:
                    interval_min = int(
                        user_db.get("reminder_offset_min") or REMINDER_DEFAULT_OFFSET_MIN
                    )
                except (TypeError, ValueError):
                    interval_min = REMINDER_DEFAULT_OFFSET_MIN
                if interval_min <= 0:
                    interval_min = REMINDER_DEFAULT_OFFSET_MIN

                # Окно отправки относительно текущего момента (минуты)
                window = max(1, REMINDER_WINDOW_MIN)
                target_min = now + timedelta(minutes=max(1, interval_min - window))
                target_max = now + timedelta(minutes=interval_min + window)

                # Состояние напоминаний (в job нельзя писать в application.user_data — mappingproxy)
                user_data = _reminder_state.get(user_id)
                if not user_data:
                    user_data = {}
                    _reminder_state[user_id] = user_data

                data, _ = await get_timetable(
                    group,
                    building=building,
                    week="current",
                    day=today_weekday,
                )
                if not data:
                    logger.debug("Напоминания: нет данных расписания для user_id=%s, группа=%s", user_id, group)
                    continue

                day_blocks = _get_day_blocks(data)
                if not day_blocks:
                    logger.debug("Напоминания: пустой блок дней для user_id=%s", user_id)
                    continue

                for day_block in day_blocks:
                    for unit in day_block.get("units", []):
                        start_str = (unit.get("start") or "").strip()
                        end_str = (unit.get("end") or "").strip()
                        
                        # Используем утилиту для исправления времени субботы
                        start_str, end_str = fix_saturday_time(start_str, end_str, today_weekday)
                        
                        lesson_start = _parse_time(start_str, today)
                        if not lesson_start:
                            logger.debug(f"Не удалось распарсить время: '{start_str}' для пользователя {user_id}")
                            continue
                        if lesson_start <= now:
                            logger.debug(f"Урок уже начался: {start_str} ({lesson_start}) <= {now} для пользователя {user_id}")
                            continue
                        if target_min <= lesson_start <= target_max:
                            logger.info(f"Найден урок для напоминания: {start_str}, текущее время: {now.strftime('%H:%M')}, день недели: {today_weekday}, пользователь: {user_id}")
                            reminder_key = f"{lesson_start.date()}_{lesson_start.hour:02d}:{lesson_start.minute:02d}"
                            if user_data.get(LAST_REMINDER_KEY) == reminder_key:
                                continue
                            # Ключ ставим только после успешной отправки, чтобы при TimedOut повторить в следующем запуске

                            # Удаляем предыдущее напоминание (если есть)
                            old_message_id = user_data.get(LAST_REMINDER_MESSAGE_ID_KEY)
                            if old_message_id:
                                try:
                                    await bot.delete_message(chat_id=user_id, message_id=old_message_id)
                                    logger.info("Удалено предыдущее напоминание для пользователя %s", user_id)
                                except BadRequest as e:
                                    # Сообщение уже удалено или недоступно
                                    logger.debug("Не удалось удалить старое напоминание для %s (уже удалено?): %s", user_id, e)
                                except TelegramError as e:
                                    # Другие ошибки Telegram API (сетевые и т.д.)
                                    logger.warning("Ошибка Telegram API при удалении напоминания для %s: %s", user_id, e)
                            
                            # Получаем язык пользователя
                            lang = get_user_language(user_id, context)
                            
                            subj = (unit.get("subject") or "—").strip()
                            room = (unit.get("room") or "").strip()
                            teacher = (unit.get("teacher") or "").strip()
                            
                            lines = [t(lang, "notifications.reminder", subject=subj)]
                            if room:
                                lines.append(t(lang, "notifications.room", room=room))
                            if teacher:
                                lines.append(t(lang, "notifications.teacher", teacher=teacher))
                            if start_str and end_str:
                                lines.append(t(lang, "notifications.time", start=start_str, end=end_str))
                            msg = "\n".join(lines)

                            # Отправка с retry при таймауте/сетевых ошибках
                            sent_message = None
                            for attempt in range(3):
                                try:
                                    sent_message = await bot.send_message(chat_id=user_id, text=msg)
                                    break
                                except (TimedOut, NetworkError) as e:
                                    if attempt < 2:
                                        logger.warning("Таймаут/сеть при отправке напоминания пользователю %s, попытка %s/3: %s", user_id, attempt + 1, e)
                                        await asyncio.sleep(2)
                                    else:
                                        logger.error("Не удалось отправить напоминание пользователю %s после 3 попыток (повторится через минуту): %s", user_id, e)

                            if sent_message:
                                user_data[LAST_REMINDER_KEY] = reminder_key
                                user_data[LAST_REMINDER_MESSAGE_ID_KEY] = sent_message.message_id
                                logger.info("Отправлено напоминание за 10 мин пользователю %s: %s", user_id, subj)
                            break
        except ValueError:
            continue
        except Exception as e:
            logger.exception("Ошибка при проверке напоминания для user_id=%s: %s", user_id, e)
