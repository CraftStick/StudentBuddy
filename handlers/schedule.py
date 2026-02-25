# -*- coding: utf-8 -*-
"""Обработчики расписания: команда /schedule и выбор дня по кнопкам."""

import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from timetable import get_timetable
from replacements import get_replacements
from config import DAY_ALIASES, MAX_MESSAGE_LENGTH, DATABASE_PATH
from keyboards import main_menu_keyboard, schedule_back_keyboard
from utils.formatters import format_timetable, format_replacements
from database import Database
from utils.user_helpers import get_user_language, get_user_group_and_building
from utils.callback_utils import safe_callback_value
from i18n import t

logger = logging.getLogger(__name__)
db = Database(db_path=DATABASE_PATH)


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /schedule — показать расписание. Можно /schedule ср или /schedule пн."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    
    # Используем helper для получения группы и корпуса
    group, building = get_user_group_and_building(user_id, context)
    
    if not group:
        await update.message.reply_text(
            t(lang, "schedule.no_group")
        )
        return

    day: int | None = None
    if context.args:
        alias = " ".join(context.args).lower().strip()
        day = DAY_ALIASES.get(alias)
        if day is None and alias.isdigit() and 0 <= int(alias) <= 5:
            day = int(alias)
        if day is None:
            await update.message.reply_text(t(lang, "schedule.unknown_day"))
            return
    else:
        w = datetime.now().weekday()
        if w >= 6:
            # Воскресенье - показываем расписание на понедельник со специальным сообщением
            await update.message.reply_text(
                "📅 Сегодня воскресенье, занятий нет.\nПоказываю расписание на понедельник:"
            )
            day = 0
        else:
            day = w

    try:
        # Параллельный запрос расписания и замен для ускорения (расписание через coalescer)
        timetable_task = get_timetable(
            group,
            building=building,
            week="current",
            day=day,
        )
        replacements_task = asyncio.to_thread(get_replacements, group, day, building)
        
        # Выполняем оба запроса параллельно
        results = await asyncio.gather(timetable_task, replacements_task, return_exceptions=True)
        
        # Обработка результата расписания
        timetable_result = results[0]
        if isinstance(timetable_result, ValueError):
            await update.message.reply_text(t(lang, "schedule.no_token"))
            logger.warning("schedule: %s", timetable_result)
            return
        elif isinstance(timetable_result, Exception):
            logger.exception("Ошибка при запросе расписания: %s", timetable_result)
            await update.message.reply_text(t(lang, "schedule.load_failed"))
            return

        data, _ = timetable_result

        if data is None:
            await update.message.reply_text(t(lang, "schedule.cache_unchanged"))
            return

        # Получаем название дня на нужном языке
        day_names_i18n = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        day_name_caption = t(lang, f"days.{day_names_i18n[day]}") if day is not None and 0 <= day <= 5 else ""
        
        if day_name_caption:
            caption = t(lang, "schedule.for_day", day=day_name_caption) + "\n\n"
        else:
            caption = "📆 Расписание\n\n"
        
        text = caption + format_timetable(data, lang)

        # Обработка результата замен
        replacements_result = results[1]
        if isinstance(replacements_result, Exception):
            logger.exception("Ошибка при запросе замен: %s", replacements_result)
            text += "\n\n✅ Нет замен"
        else:
            text += "\n\n" + format_replacements(replacements_result, lang)
    
    except Exception as e:
        logger.exception("Непредвиденная ошибка в schedule: %s", e)
        await update.message.reply_text(t(lang, "errors.unknown"))
        return

    if len(text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(text[:MAX_MESSAGE_LENGTH] + "\n\n… (обрезано)")
    else:
        await update.message.reply_text(text)


async def schedule_by_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатия кнопки дня (Пн, Вт, Ср, … или Сегодня)."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)

    # Используем helper для получения группы и корпуса
    group, building = get_user_group_and_building(user_id, context)
    
    if not group:
        await context.bot.send_message(
            update.effective_chat.id,
            t(lang, "schedule.no_group"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    # Безопасный парсинг callback_data
    value = safe_callback_value(query.data, "sched")
    if not value:
        await context.bot.send_message(
            update.effective_chat.id,
            t(lang, "schedule.format_error"),
        )
        return
    
    if value == "today":
        w = datetime.now().weekday()
        if w >= 6:
            # Воскресенье - показываем расписание на понедельник
            day = 0
        else:
            day = w
    else:
        try:
            day = int(value)
        except ValueError:
            await context.bot.send_message(
                update.effective_chat.id,
                t(lang, "schedule.invalid_day"),
            )
            return
        if day < 0 or day > 5:
            day = min(5, max(0, day))

    chat_id = update.effective_chat.id

    try:
        # Параллельный запрос расписания и замен для ускорения (расписание через coalescer)
        timetable_task = get_timetable(
            group,
            building=building,
            week="current",
            day=day,
        )
        replacements_task = asyncio.to_thread(get_replacements, group, day, building)
        
        # Выполняем оба запроса параллельно
        results = await asyncio.gather(timetable_task, replacements_task, return_exceptions=True)
        
        # Обработка результата расписания
        timetable_result = results[0]
        if isinstance(timetable_result, ValueError):
            logger.warning("schedule callback: %s", timetable_result)
            await context.bot.send_message(chat_id, t(lang, "schedule.no_token"))
            return
        elif isinstance(timetable_result, Exception):
            logger.exception("Ошибка при запросе расписания: %s", timetable_result)
            await context.bot.send_message(chat_id, t(lang, "schedule.load_failed"))
            return

        data, _ = timetable_result

        if data is None:
            await context.bot.send_message(chat_id, t(lang, "schedule.cache_unchanged_picker"))
            return

        # Получаем название дня на нужном языке
        day_names_i18n = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        day_name_caption = t(lang, f"days.{day_names_i18n[day]}") if 0 <= day <= 5 else ""
        
        if day_name_caption:
            caption = t(lang, "schedule.for_day", day=day_name_caption) + "\n\n"
        else:
            caption = "📆 Расписание\n\n"
        
        text = caption + format_timetable(data, lang)

        # Обработка результата замен
        replacements_result = results[1]
        if isinstance(replacements_result, Exception):
            logger.exception("Ошибка при запросе замен: %s", replacements_result)
            text += "\n\n✅ Нет замен"
        else:
            text += "\n\n" + format_replacements(replacements_result, lang)
    
    except Exception as e:
        logger.exception("Непредвиденная ошибка в schedule_by_day_callback: %s", e)
        await context.bot.send_message(chat_id, t(lang, "errors.unknown"))
        return

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "\n\n… (обрезано)"
    try:
        await context.bot.delete_message(chat_id, query.message.message_id)
    except BadRequest as e:
        logger.debug("delete_message (schedule_by_day_callback): %s", e)
    await context.bot.send_message(
        chat_id,
        text,
        reply_markup=schedule_back_keyboard(lang),
    )
