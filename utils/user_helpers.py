# -*- coding: utf-8 -*-
"""Вспомогательные функции для работы с данными пользователя."""

from telegram.ext import ContextTypes

from database import Database
from i18n import DEFAULT_LANGUAGE
from config import DATABASE_PATH

db = Database(db_path=DATABASE_PATH)


def load_user_data_from_db(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Загружает данные пользователя из БД в context.user_data."""
    user_db = db.get_user(user_id)
    if not user_db:
        return False
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


def ensure_user_data_loaded(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, загружены ли данные пользователя, и загружает их при необходимости."""
    has_group = context.user_data.get("group")
    has_building = context.user_data.get("building")
    has_name = context.user_data.get("name")
    if has_group and has_building and has_name:
        return True
    return load_user_data_from_db(user_id, context)


def get_user_group_and_building(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> tuple[str | None, str | None]:
    """Получает группу и корпус пользователя из context или БД."""
    group = context.user_data.get("group")
    building = context.user_data.get("building")
    if group:
        return group, building
    user_db = db.get_user(user_id)
    if user_db and user_db.get("student_group"):
        group = user_db["student_group"]
        building = user_db.get("building")
        context.user_data["group"] = group
        if building:
            context.user_data["building"] = building
        return group, building
    return None, None


def get_user_language(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Получает язык пользователя из context или БД."""
    if context.user_data is not None:
        user_data = context.user_data
    elif context.application and hasattr(context.application, "user_data"):
        user_data = context.application.user_data.get(user_id) or {}
    else:
        user_data = {}
    lang = user_data.get("language") if user_data else None
    if lang:
        return lang
    user_db = db.get_user(user_id)
    if user_db and user_db.get("language"):
        lang = user_db["language"]
        if context.application and hasattr(context.application, "user_data"):
            if context.application.user_data.get(user_id) is None:
                context.application.user_data[user_id] = {}
            context.application.user_data[user_id]["language"] = lang
        elif context.user_data is not None:
            context.user_data["language"] = lang
        return lang
    return DEFAULT_LANGUAGE
