# -*- coding: utf-8 -*-
"""Обработчики меню настроек."""

import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler

from database import Database
from keyboards import (
    settings_keyboard,
    language_keyboard,
    buildings_keyboard,
    main_menu_inline_keyboard,
    notifications_submenu_keyboard,
)
from utils.user_helpers import get_user_language
from i18n import t, SUPPORTED_LANGUAGES
from config import (
    BUILDING,
    GROUP,
    NOTIFICATIONS_ENABLED_KEY,
    DATABASE_PATH,
    REMINDER_INTERVAL_OPTIONS,
)

logger = logging.getLogger(__name__)
db = Database(db_path=DATABASE_PATH)


def _notifications_submenu_text(lang: str, enabled: bool, interval_min: int) -> str:
    """Текст экрана подменю уведомлений."""
    title = t(lang, "notifications.submenu_title")
    if enabled:
        body = t(lang, "notifications.submenu_status_on", minutes=interval_min)
    else:
        body = t(lang, "notifications.submenu_status_off")
    return f"{title}\n\n{body}"


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню настроек."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    
    await query.edit_message_text(
        t(lang, "settings_menu.title"),
        parse_mode="HTML",
        reply_markup=settings_keyboard(lang)
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка кнопок в меню настроек."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = get_user_language(user_id, context)

    data = query.data or ""
    
    if data == "settings:language":
        # Показать выбор языка
        await query.edit_message_text(
            t(lang, "settings_menu.choose_language"),
            reply_markup=language_keyboard()
        )
    
    elif data == "settings:building":
        # Начать диалог изменения корпуса
        from config import BUILDINGS_LIST
        buildings = BUILDINGS_LIST
        
        if not buildings:
            await context.bot.send_message(
                chat_id,
                t(lang, "errors.no_buildings")
            )
            return ConversationHandler.END
        
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest as e:
            logger.debug("delete_message (settings:building): %s", e)

        await context.bot.send_message(
            chat_id,
            t(lang, "welcome.choose_building"),
            reply_markup=buildings_keyboard(buildings, lang)
        )
        return BUILDING

    elif data == "settings:group":
        # Начать диалог изменения группы
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest as e:
            logger.debug("delete_message (settings:group): %s", e)
        
        await context.bot.send_message(
            chat_id,
            t(lang, "welcome.enter_group")
        )
        return GROUP
    
    elif data == "settings:notifications":
        # Открыть подменю уведомлений (интервал + вкл/выкл)
        user_db = db.get_user(user_id)
        enabled = bool(user_db.get("notifications_enabled", 1)) if user_db else True
        interval = int(user_db.get("reminder_offset_min") or 10) if user_db else 10
        if interval not in REMINDER_INTERVAL_OPTIONS:
            interval = 10
        text = _notifications_submenu_text(lang, enabled, interval)
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=notifications_submenu_keyboard(lang, enabled, from_main=False),
        )

    return ConversationHandler.END


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора языка."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Получаем выбранный язык из callback_data (формат: "lang:ru")
    parts = (query.data or "").split(":", 1)
    if len(parts) != 2:
        return
    new_lang = parts[1].strip()

    if new_lang not in SUPPORTED_LANGUAGES:
        return
    
    # Сохраняем новый язык
    db.update_user(user_id, language=new_lang)
    context.user_data["language"] = new_lang

    try:
        await context.bot.delete_message(chat_id, query.message.message_id)
    except BadRequest as e:
        logger.debug("delete_message (language_callback): %s", e)

    # Возвращаемся в главное меню с переведённым текстом (без отдельного сообщения о смене языка)
    name = context.user_data.get("name", "друг")
    group = context.user_data.get("group", "?")
    building = context.user_data.get("building", "")
    
    if building:
        msg = t(new_lang, "welcome.back_with_building", name=name, group=group, building=building)
    else:
        msg = t(new_lang, "welcome.back", name=name, group=group)
    
    await context.bot.send_message(
        chat_id,
        msg,
        reply_markup=main_menu_inline_keyboard(new_lang)
    )


async def back_to_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка «Назад» к меню настроек."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    
    await query.edit_message_text(
        t(lang, "settings_menu.title"),
        parse_mode="HTML",
        reply_markup=settings_keyboard(lang)
    )


async def notifications_submenu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработка кнопок в подменю уведомлений: вкл/выкл и интервал (5/10/15/30)."""
    query = update.callback_query
    await query.answer()
    data = (query.data or "").strip()
    if not data.startswith("notif:"):
        return
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    user_db = db.get_user(user_id)
    enabled = bool(user_db.get("notifications_enabled", 1)) if user_db else True
    interval = int(user_db.get("reminder_offset_min") or 10) if user_db else 10
    if interval not in REMINDER_INTERVAL_OPTIONS:
        interval = 10

    parts = data.split(":")
    # notif:toggle:main | notif:toggle:settings | notif:interval:10:main | notif:interval:10:settings
    if len(parts) >= 3 and parts[1] == "toggle":
        from_main = parts[2] == "main"
        new_enabled = not enabled
        db.set_notifications(user_id, new_enabled)
        context.user_data[NOTIFICATIONS_ENABLED_KEY] = new_enabled
        enabled = new_enabled
    elif len(parts) >= 4 and parts[1] == "interval":
        try:
            interval = int(parts[2])
        except ValueError:
            interval = 10
        if interval not in REMINDER_INTERVAL_OPTIONS:
            interval = 10
        db.update_user(user_id, reminder_offset_min=interval)
        from_main = parts[3] == "main"
    else:
        return

    text = _notifications_submenu_text(lang, enabled, interval)
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=notifications_submenu_keyboard(lang, enabled, from_main=from_main),
    )
