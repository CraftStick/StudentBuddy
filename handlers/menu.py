# -*- coding: utf-8 -*-
"""Обработчики главного меню и кнопок «Расписание», «Назад»."""

from telegram import Update
from telegram.ext import ContextTypes

from config import NOTIFICATIONS_ENABLED_KEY
from database import Database
from user_helpers import get_user_language
from i18n import t
from keyboards import (
    main_menu_keyboard,
    main_menu_inline_keyboard,
    schedule_day_keyboard,
)

db = Database()


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
    
    # Пытаемся взять группу из context или БД
    group = context.user_data.get("group")
    if not group:
        user_db = db.get_user(user_id)
        if user_db and user_db.get("student_group"):
            group = user_db["student_group"]
            context.user_data["group"] = group
    
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
        except Exception:
            pass
        await context.bot.send_message(
            chat_id,
            t(lang, "schedule.choose_day"),
            reply_markup=schedule_day_keyboard(lang),
        )
    elif query.data == "main:notif":
        # Получаем текущее состояние из БД
        user_db = db.get_user(user_id)
        enabled = user_db.get("notifications_enabled", 1) if user_db else True
        
        # Меняем состояние
        new_enabled = not enabled
        db.set_notifications(user_id, new_enabled)
        context.user_data[NOTIFICATIONS_ENABLED_KEY] = new_enabled
        
        text = t(lang, "notifications.enabled" if new_enabled else "notifications.disabled")
        await context.bot.send_message(chat_id, text)


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка «Назад»: удаляем текущее сообщение и показываем предыдущий экран."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        await context.bot.delete_message(chat_id, query.message.message_id)
    except Exception:
        pass
    
    lang = get_user_language(user_id, context)
    
    if query.data == "back:main":
        # Загружаем данные из БД если их нет в context
        name = context.user_data.get("name")
        group = context.user_data.get("group")
        building = context.user_data.get("building")
        
        if not name or not group:
            user_db = db.get_user(user_id)
            if user_db:
                name = user_db.get("name", "друг")
                group = user_db.get("student_group", "?")
                building = user_db.get("building", "")
                context.user_data["name"] = name
                context.user_data["group"] = group
                context.user_data["building"] = building
            else:
                name = "друг"
                group = "?"
                building = ""
        
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
    
    # Пытаемся взять группу из context или БД
    group = context.user_data.get("group")
    if not group:
        user_db = db.get_user(user_id)
        if user_db and user_db.get("student_group"):
            group = user_db["student_group"]
            context.user_data["group"] = group
        else:
            await update.message.reply_text(
                t(lang, "schedule.no_group"),
                reply_markup=main_menu_keyboard(lang),
            )
            return
    await update.message.reply_text(
        t(lang, "schedule.choose_day"),
        reply_markup=schedule_day_keyboard(lang),
    )
