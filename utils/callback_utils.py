# -*- coding: utf-8 -*-
"""Утилиты для работы с callback_data."""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def parse_callback_data(callback_data: str, expected_prefix: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Безопасный парсинг callback_data с валидацией формата."""
    if not callback_data or not isinstance(callback_data, str):
        logger.warning("Некорректный callback_data: %s", callback_data)
        return None, None
    parts = callback_data.split(":", 1)
    if len(parts) != 2:
        logger.warning("Некорректный формат callback_data (ожидается 'prefix:value'): %s", callback_data)
        return None, None
    prefix, value = parts
    if expected_prefix and prefix != expected_prefix:
        logger.warning("Неожиданный префикс в callback_data: получен '%s', ожидался '%s'", prefix, expected_prefix)
        return None, None
    return prefix, value


def safe_callback_value(callback_data: str, expected_prefix: str, default: str = "") -> str:
    """Получить значение из callback_data с валидацией."""
    prefix, value = parse_callback_data(callback_data, expected_prefix)
    if value is None:
        return default
    return value
