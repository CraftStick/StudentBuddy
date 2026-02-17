# -*- coding: utf-8 -*-
"""Напоминания за 10 минут до начала урока."""

import asyncio
import logging
from datetime import datetime, timedelta

from telegram.ext import ContextTypes

from timetable import get_timetable
from config import NOTIFICATIONS_ENABLED_KEY, LAST_REMINDER_KEY, LAST_REMINDER_MESSAGE_ID_KEY, SCHEDULE_TIMEZONE
from database import Database
from user_helpers import get_user_language
from i18n import t

logger = logging.getLogger(__name__)
db = Database()


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
        return
    target_min = now + timedelta(minutes=9)
    target_max = now + timedelta(minutes=11)
    today = now  # дата и время «сейчас» в поясе расписания (для парсинга времени урока)

    # Получаем всех пользователей с включенными уведомлениями из БД
    try:
        users = db.get_users_with_notifications()
    except Exception as e:
        logger.exception("Ошибка при получении пользователей из БД: %s", e)
        return

    for user_db in users:
        user_id = user_db.get("user_id")
        if not user_id:
            continue
        
        try:
            group = user_db.get("student_group")
            if not group or not isinstance(group, str):
                continue
            
            building = user_db.get("building")
            
            # Получаем user_data для хранения состояния последнего напоминания
            user_data = application.user_data.get(user_id)
            if not user_data:
                user_data = {}
                application.user_data[user_id] = user_data
            
            data, _ = await asyncio.to_thread(
                get_timetable,
                group,
                building=building,
                week="current",
                day=today_weekday,
            )
            if not data:
                continue

            for day_block in data.get("data", []):
                for unit in day_block.get("units", []):
                    start_str = (unit.get("start") or "").strip()
                    
                    # Костыль: API возвращает неправильное время для субботы (8:30 вместо 9:00)
                    if today_weekday == 5 and start_str == "8:30":
                        start_str = "9:00"
                        logger.info(f"Исправлено время для субботы: 8:30 -> 9:00 для пользователя {user_id}")
                    
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
                        user_data[LAST_REMINDER_KEY] = reminder_key

                        # Удаляем предыдущее напоминание (если есть)
                        old_message_id = user_data.get(LAST_REMINDER_MESSAGE_ID_KEY)
                        if old_message_id:
                            try:
                                await bot.delete_message(chat_id=user_id, message_id=old_message_id)
                                logger.info("Удалено предыдущее напоминание для пользователя %s", user_id)
                            except Exception as e:
                                logger.warning("Не удалось удалить старое напоминание для %s: %s", user_id, e)
                        
                        # Получаем язык пользователя
                        lang = get_user_language(user_id, context)
                        
                        subj = (unit.get("subject") or "—").strip()
                        room = (unit.get("room") or "").strip()
                        teacher = (unit.get("teacher") or "").strip()
                        end_str = (unit.get("end") or "").strip()
                        
                        lines = [t(lang, "notifications.reminder", subject=subj)]
                        if room:
                            lines.append(t(lang, "notifications.room", room=room))
                        if teacher:
                            lines.append(t(lang, "notifications.teacher", teacher=teacher))
                        if start_str and end_str:
                            lines.append(t(lang, "notifications.time", start=start_str, end=end_str))
                        msg = "\n".join(lines)
                        sent_message = await bot.send_message(chat_id=user_id, text=msg)
                        
                        # Сохраняем ID нового напоминания
                        user_data[LAST_REMINDER_MESSAGE_ID_KEY] = sent_message.message_id
                        
                        logger.info("Отправлено напоминание за 10 мин пользователю %s: %s", user_id, subj)
                        break
        except ValueError:
            continue
        except Exception as e:
            logger.exception("Ошибка при проверке напоминания для user_id=%s: %s", user_id, e)
