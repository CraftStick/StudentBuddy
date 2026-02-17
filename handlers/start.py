# -*- coding: utf-8 -*-
"""Обработчики команды /start и диалога выбора корпуса и группы."""

import logging
import os

import httpx
from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes

from config import BUILDING, GROUP, BUILDINGS_LIST, GROUP_PATTERN
from database import Database
from user_helpers import get_user_language
from i18n import t
from keyboards import (
    buildings_keyboard,
    group_back_keyboard,
    main_menu_inline_keyboard,
    main_menu_keyboard,
)

logger = logging.getLogger(__name__)
db = Database()


def _user_display_name(user) -> str:
    """Имя для приветствия: first_name, иначе username, иначе «друг»."""
    if user.first_name and user.first_name.strip():
        return user.first_name.strip()
    if user.username and user.username.strip():
        return user.username.strip()
    return "друг"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /start — приветствие. Если уже в БД с группой — сразу меню, иначе выбор корпуса и группы."""
    user = update.effective_user
    name = _user_display_name(user)
    
    # Добавляем или обновляем пользователя в БД
    if not db.user_exists(user.id):
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            name=name
        )
    else:
        # Обновляем имя на случай, если пользователь изменил его
        db.update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            name=name
        )
    
    context.user_data["name"] = name
    
    # Получаем язык пользователя
    lang = get_user_language(user.id, context)
    
    # Если пользователь уже в БД с группой и корпусом — не спрашиваем заново, сразу главное меню
    user_db = db.get_user(user.id)
    if user_db and user_db.get("student_group") and user_db.get("building"):
        context.user_data["group"] = user_db["student_group"]
        context.user_data["building"] = user_db["building"]
        group = user_db["student_group"]
        building = user_db["building"]
        msg = t(lang, "welcome.back_with_building", name=name, group=group, building=building)
        await update.message.reply_text(
            msg,
            reply_markup=main_menu_inline_keyboard(lang),
        )
        return ConversationHandler.END
    
    # Новый пользователь или без группы — просим выбрать корпус
    context.user_data["buildings_list"] = BUILDINGS_LIST
    greeting = t(lang, "welcome.hello", name=name)
    choose_building = t(lang, "welcome.choose_building")
    await update.message.reply_text(
        f"{greeting}\n\n{choose_building}",
        reply_markup=buildings_keyboard(BUILDINGS_LIST, lang),
    )
    return BUILDING


async def back_to_building(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Кнопка «Назад» на шаге ввода группы — возврат к выбору корпуса."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    buildings_list = context.user_data.get("buildings_list") or BUILDINGS_LIST
    await query.edit_message_text(
        t(lang, "welcome.choose_building"),
        reply_markup=buildings_keyboard(buildings_list, lang),
    )
    return BUILDING


async def receive_building_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор корпуса по нажатию инлайн-кнопки."""
    query = update.callback_query
    await query.answer()
    try:
        _, building = query.data.split(":", 1)
    except ValueError:
        return BUILDING
    
    # Сохраняем корпус в context и БД
    context.user_data["building"] = building
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    db.update_user(user_id, building=building)
    
    msg = t(lang, "welcome.enter_group")
    await query.edit_message_text(
        msg,
        reply_markup=group_back_keyboard(lang),
    )
    return GROUP


async def receive_building(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение корпуса текстом (если совпадает с одним из списка API)."""
    text = update.message.text.strip()
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    buildings_list = context.user_data.get("buildings_list") or []
    if not buildings_list:
        await update.message.reply_text(t(lang, "errors.no_buildings"))
        return BUILDING
    if text in buildings_list:
        # Сохраняем корпус в context и БД
        context.user_data["building"] = text
        db.update_user(user_id, building=text)
        
        await update.message.reply_text(
            t(lang, "welcome.enter_group"),
            reply_markup=group_back_keyboard(lang),
        )
        return GROUP
    await update.message.reply_text(
        t(lang, "welcome.choose_building"),
        reply_markup=buildings_keyboard(buildings_list, lang),
    )
    return BUILDING


async def receive_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение группы, проверка формата и существования в выбранном корпусе."""
    group = update.message.text.strip()
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    
    if not GROUP_PATTERN.match(group):
        await update.message.reply_text(t(lang, "errors.invalid_group"))
        return GROUP
    
    # Проверяем, существует ли группа в выбранном корпусе
    building = context.user_data.get("building", "")
    token = os.getenv("SCHEDULE_API_TOKEN")
    
    if not token:
        logger.error("SCHEDULE_API_TOKEN не найден")
        context.user_data["group"] = group
        db.update_user(user_id, student_group=group)
        name = context.user_data.get("name", "друг")
        if building:
            done_msg = t(lang, "welcome.back_with_building", name=name, group=group, building=building)
        else:
            done_msg = t(lang, "welcome.back", name=name, group=group)
        await update.message.reply_text(done_msg, reply_markup=main_menu_inline_keyboard(lang))
        return ConversationHandler.END
    
    # Асинхронная проверка группы через API
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.mgkeit.space/api/v1/timetable",
                json={"group": group, "building": building, "week": "current"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            
            logger.info(f"API ответ для группы {group} в корпусе {building}: статус {resp.status_code}")
            
            if resp.status_code == 404:
                # Группа не найдена
                await update.message.reply_text(
                    t(lang, "errors.group_not_found", group=group, building=building),
                    reply_markup=group_back_keyboard(lang),
                )
                return GROUP
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"Данные от API: {data}")
                
                # Проверяем, что корпус в ответе совпадает с выбранным
                api_building = data.get("meta", {}).get("building", "")
                if api_building != building:
                    await update.message.reply_text(
                        t(lang, "errors.wrong_building", group=group, building=building, api_building=api_building),
                        reply_markup=group_back_keyboard(lang),
                    )
                    return GROUP
                
                # Проверяем, есть ли расписание
                if not data.get("data") or len(data.get("data", [])) == 0:
                    await update.message.reply_text(
                        t(lang, "errors.group_not_found", group=group, building=building),
                        reply_markup=group_back_keyboard(lang),
                    )
                    return GROUP
            
            resp.raise_for_status()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP ошибка при проверке группы: {e}")
        await update.message.reply_text(
            t(lang, "errors.group_not_found", group=group, building=building),
            reply_markup=group_back_keyboard(lang),
        )
        return GROUP
    except Exception as e:
        logger.error(f"Ошибка при проверке группы: {e}")
        # Если ошибка сети, разрешаем продолжить
        pass
    
    # Сохраняем группу в context и БД
    context.user_data["group"] = group
    db.update_user(user_id, student_group=group)
    
    name = context.user_data.get("name", "друг")
    if building:
        done_msg = t(lang, "welcome.back_with_building", name=name, group=group, building=building)
    else:
        done_msg = t(lang, "welcome.back", name=name, group=group)
    await update.message.reply_text(done_msg, reply_markup=main_menu_inline_keyboard(lang))
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена диалога."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    # Добавим простую строку для отмены в локали
    await update.message.reply_text("Ок, в любой момент можно начать заново — нажми /start")
    return ConversationHandler.END


async def cancel_or_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Реакция на кнопку «❌ Отмена» вне диалога."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    # Добавим простую строку в локали
    await update.message.reply_text(
        "Сейчас нечего отменять. Используй кнопки ниже или /menu.",
        reply_markup=main_menu_keyboard(lang),
    )


async def reply_finish_building(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ответ при нажатии «📅 Расписание» на шаге выбора корпуса."""
    await update.message.reply_text("Сначала укажи корпус, затем группу. Или нажми «❌ Отмена».")
    return BUILDING


async def reply_finish_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ответ при нажатии «📅 Расписание» на шаге ввода группы."""
    await update.message.reply_text("Сначала введи группу или нажми «❌ Отмена».")
    return GROUP
