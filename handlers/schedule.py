# -*- coding: utf-8 -*-
"""Обработчики расписания: команда /schedule и выбор дня по кнопкам."""

import asyncio
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from timetable import get_timetable
from replacements import get_replacements
from config import DAY_ALIASES, DAY_NAMES
from keyboards import main_menu_keyboard, schedule_back_keyboard
from formatters import format_timetable, format_replacements
from database import Database
from user_helpers import get_user_language
from i18n import t

logger = logging.getLogger(__name__)
db = Database()


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /schedule — показать расписание. Можно /schedule ср или /schedule пн."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    
    # Сначала пытаемся взять из context, если нет - из БД
    group = context.user_data.get("group")
    building = context.user_data.get("building")
    
    if not group:
        # Пытаемся загрузить из БД
        user_db = db.get_user(user_id)
        if user_db and user_db.get("student_group"):
            group = user_db["student_group"]
            building = user_db.get("building")
            # Сохраняем в context для быстрого доступа
            context.user_data["group"] = group
            context.user_data["building"] = building
        else:
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
            await update.message.reply_text(
                "Неизвестный день. Укажи: пн, вт, ср, чт, пт, сб или число 0–5."
            )
            return
    else:
        w = datetime.now().weekday()
        day = w if w <= 5 else 5

    try:
        data, _ = await asyncio.to_thread(
            get_timetable,
            group,
            building=building,
            week="current",
            day=day,
        )
    except ValueError as e:
        await update.message.reply_text(
            "Не настроен токен расписания (SCHEDULE_API_TOKEN). Обратись к администратору."
        )
        logger.warning("schedule: %s", e)
        return
    except Exception as e:
        logger.exception("Ошибка при запросе расписания: %s", e)
        await update.message.reply_text(
            "Не удалось загрузить расписание. Попробуй позже или проверь корпус и группу (/start)."
        )
        return

    if data is None:
        await update.message.reply_text(
            "Данные не изменились (кэш). Нажми «📅 Расписание» и выбери день кнопкой."
        )
        return

    # Получаем название дня на нужном языке
    day_names_i18n = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    day_name_caption = t(lang, f"days.{day_names_i18n[day]}") if day is not None and 0 <= day <= 5 else ""
    
    if day_name_caption:
        caption = t(lang, "schedule.for_day", day=day_name_caption) + "\n\n"
    else:
        caption = "📆 Расписание\n\n"
    
    text = caption + format_timetable(data, lang)

    try:
        replacements = await asyncio.to_thread(get_replacements, group, day, building)
        text += "\n\n" + format_replacements(replacements)
    except Exception as e:
        logger.exception("Ошибка при запросе замен: %s", e)
        text += "\n\n✅ Нет замен"

    if len(text) > 4000:
        await update.message.reply_text(text[:4000] + "\n\n… (обрезано)")
    else:
        await update.message.reply_text(text)


async def schedule_by_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатия кнопки дня (Пн, Вт, Ср, … или Сегодня)."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)

    # Сначала пытаемся взять из context, если нет - из БД
    group = context.user_data.get("group")
    building = context.user_data.get("building")
    
    if not group:
        # Пытаемся загрузить из БД
        user_db = db.get_user(user_id)
        if user_db and user_db.get("student_group"):
            group = user_db["student_group"]
            building = user_db.get("building")
            # Сохраняем в context для быстрого доступа
            context.user_data["group"] = group
            context.user_data["building"] = building
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                t(lang, "schedule.no_group"),
                reply_markup=main_menu_keyboard(lang),
            )
            return
    try:
        _, value = query.data.split(":", 1)
    except ValueError:
        await context.bot.send_message(
            update.effective_chat.id,
            "Ошибка формата. Нажми «📅 Расписание» и выбери день кнопкой.",
        )
        return
    if value == "today":
        w = datetime.now().weekday()
        day = w if w <= 5 else 5
    else:
        try:
            day = int(value)
        except ValueError:
            await context.bot.send_message(
                update.effective_chat.id,
                "Неверный день. Нажми «📅 Расписание» и выбери день кнопкой.",
            )
            return
        if day < 0 or day > 5:
            day = min(5, max(0, day))

    try:
        data, _ = await asyncio.to_thread(
            get_timetable,
            group,
            building=building,
            week="current",
            day=day,
        )
    except ValueError as e:
        logger.warning("schedule callback: %s", e)
        await context.bot.send_message(
            update.effective_chat.id,
            "Не настроен токен расписания (SCHEDULE_API_TOKEN). Обратись к администратору.",
        )
        return
    except Exception as e:
        logger.exception("Ошибка при запросе расписания: %s", e)
        await context.bot.send_message(
            update.effective_chat.id,
            "Не удалось загрузить расписание. Попробуй позже или проверь корпус и группу (/start).",
        )
        return

    if data is None:
        await context.bot.send_message(
            update.effective_chat.id,
            "Данные не изменились (кэш). Выбери другой день кнопкой «📅 Расписание».",
        )
        return

    # Получаем название дня на нужном языке
    day_names_i18n = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    day_name_caption = t(lang, f"days.{day_names_i18n[day]}") if 0 <= day <= 5 else ""
    
    if day_name_caption:
        caption = t(lang, "schedule.for_day", day=day_name_caption) + "\n\n"
    else:
        caption = "📆 Расписание\n\n"
    
    text = caption + format_timetable(data, lang)

    try:
        replacements = await asyncio.to_thread(get_replacements, group, day, building)
        text += "\n\n" + format_replacements(replacements, lang)
    except Exception as e:
        logger.exception("Ошибка при запросе замен: %s", e)
        text += "\n\n✅ Нет замен"

    if len(text) > 4000:
        text = text[:4000] + "\n\n… (обрезано)"
    try:
        await context.bot.delete_message(update.effective_chat.id, query.message.message_id)
    except Exception:
        pass
    await context.bot.send_message(
        update.effective_chat.id,
        text,
        reply_markup=schedule_back_keyboard(lang),
    )
