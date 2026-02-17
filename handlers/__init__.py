# -*- coding: utf-8 -*-
"""Обработчики команд и callback-кнопок бота."""

from handlers.start import (
    start,
    back_to_building,
    receive_building_callback,
    receive_building,
    receive_group,
    cancel,
    cancel_or_ok,
    reply_finish_building,
    reply_finish_group,
)
from handlers.menu import menu, main_menu_callback, back_callback, schedule_day_picker
from handlers.schedule import schedule, schedule_by_day_callback
from handlers.reminders import send_lesson_reminders
from handlers.errors import error_handler
from handlers.settings import settings_menu, settings_callback, language_callback, back_to_settings

__all__ = [
    "start",
    "back_to_building",
    "receive_building_callback",
    "receive_building",
    "receive_group",
    "cancel",
    "cancel_or_ok",
    "reply_finish_building",
    "reply_finish_group",
    "menu",
    "main_menu_callback",
    "back_callback",
    "schedule_day_picker",
    "schedule",
    "schedule_by_day_callback",
    "send_lesson_reminders",
    "error_handler",
    "settings_menu",
    "settings_callback",
    "language_callback",
    "back_to_settings",
]
