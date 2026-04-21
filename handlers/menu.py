# -*- coding: utf-8 -*-
"""Обработчики главного меню и кнопок «Расписание», «Назад»."""

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import logging

from config import DATABASE_PATH
from database import Database
from utils.user_helpers import get_user_language, get_user_group_and_building, ensure_user_data_loaded
from i18n import t
from keyboards import (
    main_menu_keyboard,
    main_menu_inline_keyboard,
    schedule_day_keyboard,
    buses_keyboard,
    notifications_submenu_keyboard,
)
from handlers.settings import _notifications_submenu_text
from config import REMINDER_INTERVAL_OPTIONS

logger = logging.getLogger(__name__)
db = Database(db_path=DATABASE_PATH)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главное меню. Команда /menu — описание, кнопки под сообщениями."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    msg = t(lang, "menu.main")
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка инлайн-кнопок под сообщением: «📅 Расписание» и «🔔 Уведомления»."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Используем helper для получения группы и корпуса
    group, _ = get_user_group_and_building(user_id, context)
    lang = get_user_language(user_id, context)
    
    if query.data == "main:sched":
        if not group:
            await context.bot.send_message(
                chat_id,
                t(lang, "schedule.no_group"),
            )
            return
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest as e:
            logger.debug("delete_message (main:sched): %s", e)
        await context.bot.send_message(
            chat_id,
            t(lang, "schedule.choose_day"),
            reply_markup=schedule_day_keyboard(lang),
        )
    elif query.data == "main:notif":
        # Открыть подменю уведомлений (интервал + вкл/выкл)
        user_db = db.get_user(user_id)
        enabled = bool(user_db.get("notifications_enabled", 1)) if user_db else True
        interval = int(user_db.get("reminder_offset_min") or 10) if user_db else 10
        if interval not in REMINDER_INTERVAL_OPTIONS:
            interval = 10
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest as e:
            logger.debug("delete_message (main:notif): %s", e)
        text = _notifications_submenu_text(lang, enabled, interval)
        await context.bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=notifications_submenu_keyboard(lang, enabled, from_main=True),
        )
    elif query.data == "main:buses":
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest as e:
            logger.debug("delete_message (main:buses): %s", e)
        await context.bot.send_message(
            chat_id,
            t(lang, "buses.choose_direction"),
            parse_mode="HTML",
            reply_markup=buses_keyboard(lang),
        )


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка «Назад»: удаляем текущее сообщение и показываем предыдущий экран."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        await context.bot.delete_message(chat_id, query.message.message_id)
    except BadRequest as e:
        logger.debug("delete_message (back_callback): %s", e)

    lang = get_user_language(user_id, context)

    if query.data == "back:main":
        # Загружаем данные из БД если их нет в context
        ensure_user_data_loaded(user_id, context)
        
        name = context.user_data.get("name", "друг")
        group = context.user_data.get("group", "?")
        building = context.user_data.get("building", "")
        
        if building:
            msg = t(lang, "welcome.back_with_building", name=name, group=group, building=building)
        else:
            msg = t(lang, "welcome.back", name=name, group=group)
        await context.bot.send_message(chat_id, msg, reply_markup=main_menu_inline_keyboard(lang))
    elif query.data == "back:day_picker":
        await context.bot.send_message(
            chat_id,
            t(lang, "schedule.choose_day"),
            reply_markup=schedule_day_keyboard(lang),
        )


async def schedule_day_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать выбор дня недели кнопками (по нажатию «📅 Расписание»)."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)

    group, _ = get_user_group_and_building(user_id, context)
    if not group:
        await update.message.reply_text(
            t(lang, "schedule.no_group"),
            reply_markup=main_menu_keyboard(lang),
        )
        return

    await update.message.reply_text(
        t(lang, "schedule.choose_day"),
        reply_markup=schedule_day_keyboard(lang),
    )
