# -*- coding: utf-8 -*-
"""Вспомогательные функции и утилиты."""

from utils.user_helpers import (
    load_user_data_from_db,
    ensure_user_data_loaded,
    get_user_group_and_building,
    get_user_language,
)
from utils.callback_utils import parse_callback_data, safe_callback_value
from utils.time_utils import fix_saturday_time
from utils.formatters import (
    safe_strip,
    subject_emoji,
    week_label,
    format_timetable,
    format_replacements,
)

__all__ = [
    "load_user_data_from_db",
    "ensure_user_data_loaded",
    "get_user_group_and_building",
    "get_user_language",
    "parse_callback_data",
    "safe_callback_value",
    "fix_saturday_time",
    "safe_strip",
    "subject_emoji",
    "week_label",
    "format_timetable",
    "format_replacements",
]
