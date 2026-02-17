# -*- coding: utf-8 -*-
"""Обработчики меню настроек."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from database import Database
from keyboards import settings_keyboard, language_keyboard, buildings_keyboard, main_menu_inline_keyboard
from user_helpers import get_user_language
from i18n import t, SUPPORTED_LANGUAGES
from config import BUILDING, GROUP

db = Database()


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
    
    if query.data == "settings:language":
        # Показать выбор языка
        await query.edit_message_text(
            t(lang, "settings_menu.choose_language"),
            reply_markup=language_keyboard()
        )
    
    elif query.data == "settings:building":
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
        except Exception:
            pass
        
        await context.bot.send_message(
            chat_id,
            t(lang, "welcome.choose_building"),
            reply_markup=buildings_keyboard(buildings, lang)
        )
        return BUILDING
    
    elif query.data == "settings:group":
        # Начать диалог изменения группы
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except Exception:
            pass
        
        await context.bot.send_message(
            chat_id,
            t(lang, "welcome.enter_group")
        )
        return GROUP
    
    elif query.data == "settings:notifications":
        # Переключить уведомления
        user_db = db.get_user(user_id)
        enabled = user_db.get("notifications_enabled", 1) if user_db else True
        
        new_enabled = not enabled
        db.set_notifications(user_id, new_enabled)
        from config import NOTIFICATIONS_ENABLED_KEY
        context.user_data[NOTIFICATIONS_ENABLED_KEY] = new_enabled
        
        text = t(lang, "notifications.enabled" if new_enabled else "notifications.disabled")
        
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except Exception:
            pass
        
        await context.bot.send_message(chat_id, text)
        
        # Вернуться в главное меню
        name = context.user_data.get("name", "друг")
        group = context.user_data.get("group", "?")
        building = context.user_data.get("building", "")
        
        if building:
            msg = t(lang, "welcome.back_with_building", name=name, group=group, building=building)
        else:
            msg = t(lang, "welcome.back", name=name, group=group)
        
        await context.bot.send_message(
            chat_id,
            msg,
            reply_markup=main_menu_inline_keyboard(lang)
        )
    
    return ConversationHandler.END


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора языка."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Получаем выбранный язык из callback_data (формат: "lang:ru")
    new_lang = query.data.split(":")[1]
    
    if new_lang not in SUPPORTED_LANGUAGES:
        return
    
    # Сохраняем новый язык
    db.update_user(user_id, language=new_lang)
    context.user_data["language"] = new_lang
    
    # Показываем подтверждение
    lang_name = SUPPORTED_LANGUAGES[new_lang]
    text = t(new_lang, "settings_menu.language_selected", language=lang_name)
    
    try:
        await context.bot.delete_message(chat_id, query.message.message_id)
    except Exception:
        pass
    
    await context.bot.send_message(chat_id, text)
    
    # Возвращаемся в главное меню с переведённым текстом
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
