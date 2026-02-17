# -*- coding: utf-8 -*-
"""Вспомогательные функции для работы с данными пользователя."""

from telegram.ext import ContextTypes
from database import Database
from i18n import DEFAULT_LANGUAGE

db = Database()


def load_user_data_from_db(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Загружает данные пользователя из БД в context.user_data.
    
    Args:
        user_id: ID пользователя Telegram
        context: Контекст бота
        
    Returns:
        True если данные загружены, False если пользователь не найден в БД
    """
    user_db = db.get_user(user_id)
    if not user_db:
        return False
    
    # Загружаем данные в context
    if user_db.get("name"):
        context.user_data["name"] = user_db["name"]
    if user_db.get("student_group"):
        context.user_data["group"] = user_db["student_group"]
    if user_db.get("building"):
        context.user_data["building"] = user_db["building"]
    if user_db.get("language"):
        context.user_data["language"] = user_db["language"]
    if "notifications_enabled" in user_db:
        from config import NOTIFICATIONS_ENABLED_KEY
        context.user_data[NOTIFICATIONS_ENABLED_KEY] = bool(user_db["notifications_enabled"])
    
    return True


def ensure_user_data_loaded(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Проверяет, загружены ли данные пользователя, и загружает их при необходимости.
    
    Args:
        user_id: ID пользователя Telegram
        context: Контекст бота
    """
    # Если данные уже есть в context, ничего не делаем
    if context.user_data.get("group"):
        return
    
    # Пытаемся загрузить из БД
    load_user_data_from_db(user_id, context)


def get_user_language(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Получает язык пользователя из context или БД.
    
    Args:
        user_id: ID пользователя Telegram
        context: Контекст бота
        
    Returns:
        Код языка (ru, en, de, no, sv, fi)
    """
    # Сначала проверяем context
    lang = context.user_data.get("language")
    if lang:
        return lang
    
    # Загружаем из БД
    user_db = db.get_user(user_id)
    if user_db and user_db.get("language"):
        lang = user_db["language"]
        context.user_data["language"] = lang
        return lang
    
    # Возвращаем язык по умолчанию
    return DEFAULT_LANGUAGE
