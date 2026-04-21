# -*- coding: utf-8 -*-
"""Обработчик ошибок бота."""

import logging

from telegram import Update
from telegram.error import NetworkError
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(
    update: object, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработчик ошибок: логирует и при сетевых сбоях не падает."""
    err = context.error
    if isinstance(err, NetworkError):
        logger.warning("Сетевая ошибка (восстановление автоматически): %s", err)
        return
    logger.exception("Ошибка при обработке апдейта: %s", err)
    if update is not None and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Произошла ошибка. Попробуй /start или /menu позже."
            )
        except Exception as e:
            logger.debug("Не удалось отправить сообщение об ошибке пользователю: %s", e)
