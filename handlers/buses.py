# -*- coding: utf-8 -*-
"""Обработчики меню «Автобусы» — расписание с Яндекс.Карт (парсер mosgortrans).

Для работы парсера нужны:
- Playwright (pip install playwright && playwright install chromium) — управление браузером.
Без установленного Chromium расписание с сайта подгружаться не будет.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from utils.user_helpers import get_user_language
from i18n import t
from keyboards import buses_keyboard

logger = logging.getLogger(__name__)

# Направления: URL, подпись остановки, автобусы, маршрут «от — до», кол-во остановок по маршрутам
# Кэш расписания по направлению: (direction -> (text, expires_at)), TTL 75 сек
_BUS_SCHEDULE_CACHE: dict[str, tuple[str, float]] = {}
_BUS_CACHE_TTL = 75


def _get_cached_schedule(direction: str) -> str | None:
    """Возвращает закэшированный текст расписания или None."""
    now = time.time()
    if direction not in _BUS_SCHEDULE_CACHE:
        return None
    text, expires_at = _BUS_SCHEDULE_CACHE[direction]
    if now > expires_at:
        del _BUS_SCHEDULE_CACHE[direction]
        return None
    return text


def _set_cached_schedule(direction: str, text: str) -> None:
    """Сохраняет результат в кэш только при успешном ответе."""
    if not text or "не сконфигурирован" in text or "не найдено" in text:
        return
    _BUS_SCHEDULE_CACHE[direction] = (text, time.time() + _BUS_CACHE_TTL)


BUS_DIRECTIONS = {
    "home_office": {
        "url": "https://yandex.ru/maps/213/moscow/stops/stop__9643158/?ll=37.663089%2C55.676860&tab=overview&z=18",
        "message": "Метро Коломенская · 3A",
        "buses": ["м19", "с820"],
        "route_from_to": "От метро Коломенская до Электромеханический колледж",
        "stops": {"м19": 5, "с820": 5},
    },
    "office_home": {
        "url": "https://yandex.ru/maps/213/moscow/stops/stop__9645789/?ll=37.648561%2C55.665797&tab=overview&z=20",
        "message": "Коломенский проезд, 8",
        "buses": ["с820"],
        "route_from_to": "От Коломенский проезд, 8 до метро Коломенская",
        "stops": {"с820": 4},
    },
}


def _fetch_bus_schedule_sync(direction: str) -> str:
    """Синхронный вызов парсера mosgortrans (выполняется в executor).
    Использует Playwright + Chromium.
    """
    root = Path(__file__).resolve().parent.parent
    mosgortrans_root = root / "parser" / "mosgortrans-master"
    if not mosgortrans_root.is_dir():
        logger.warning("mosgortrans-master not found at %s", mosgortrans_root)
        return ""

    if str(mosgortrans_root) not in sys.path:
        sys.path.insert(0, str(mosgortrans_root))

    try:
        from app.core.parse_web import WebParser  # type: ignore[reportMissingImports]

        cfg = BUS_DIRECTIONS.get(direction)
        if not cfg:
            return ""
        with WebParser.get_browser_context() as page:
            result = WebParser.parse_yandex_maps(
                url=cfg["url"],
                message=cfg["message"],
                buses=cfg["buses"],
                page=page,
            )
        if "не сконфигурирован" in result:
            logger.debug("Web parser not available, bus schedule from site disabled")
        return result
    except ImportError as e:
        logger.warning("Playwright not installed or parse_web unavailable: %s", e)
        return "не сконфигурирован"
    except Exception as e:
        err_msg = str(e).lower()
        # Playwright/Chromium не установлен: "executable doesn't exist", "browser not found" и т.п.
        if "executable" in err_msg or (
            "browser" in err_msg
            and ("not found" in err_msg or "doesn't exist" in err_msg or "not installed" in err_msg)
        ):
            logger.warning("Playwright Chromium not installed or not found: %s", e)
            return "не сконфигурирован"
        logger.exception("Bus schedule fetch failed: %s", e)
        return ""


async def buses_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать меню выбора направления (К колледжу / К метро)."""
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        lang = get_user_language(user_id, context)
        if query.message:
            try:
                await context.bot.delete_message(chat_id, query.message.message_id)
            except BadRequest:
                pass
        await context.bot.send_message(
            chat_id,
            t(lang, "buses.choose_direction"),
            parse_mode="HTML",
            reply_markup=buses_keyboard(lang),
        )
        return

    # Вызвано по кнопке под полем ввода (Reply)
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)
    await update.message.reply_text(
        t(lang, "buses.choose_direction"),
        parse_mode="HTML",
        reply_markup=buses_keyboard(lang),
    )


async def buses_direction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """По нажатию «К колледжу» или «К метро» — парсим расписание и отправляем."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    lang = get_user_language(user_id, context)

    # Удаляем сообщение «Выбери направление» с кнопками (если ещё есть)
    if query.message:
        try:
            await context.bot.delete_message(chat_id, query.message.message_id)
        except BadRequest:
            pass

    # Только разрешённые направления — защита от поддельного callback_data
    direction = query.data.split(":", 1)[-1] if query.data else ""
    if direction not in BUS_DIRECTIONS:
        await context.bot.send_message(
            chat_id,
            t(lang, "buses.error"),
            reply_markup=buses_keyboard(lang),
        )
        return

    loading_msg = await context.bot.send_message(chat_id, t(lang, "buses.loading"))

    cached = _get_cached_schedule(direction)
    if cached is not None:
        text = cached
    else:
        loop = asyncio.get_event_loop()
        try:
            text = await loop.run_in_executor(
                None,
                _fetch_bus_schedule_sync,
                direction,
            )
            if text and "не сконфигурирован" not in text and "не найдено" not in text:
                _set_cached_schedule(direction, text)
        except Exception as e:
            logger.exception("Bus schedule task failed: %s", e)
            text = ""

    cfg = BUS_DIRECTIONS.get(direction, {})

    if not text or "не сконфигурирован" in text or "не найдено" in text:
        url = cfg.get("url", "")
        # Различаем: нет Firefox на сервере vs сетевая/другая ошибка
        if text and "не сконфигурирован" in text:
            text = t(lang, "buses.error_no_driver")
        else:
            text = t(lang, "buses.error")
        if url:
            text += f"\n\n{url}"
    else:
        # Успешный ответ: маршрут и остановки уже в заголовке — убираем повтор названия остановки из вывода парсера
        msg = cfg.get("message", "")
        if msg and text.startswith(msg):
            text = text[len(msg):].lstrip("\n")
        title = t(lang, "buses.to_college") if direction == "home_office" else t(lang, "buses.to_metro")
        route = cfg.get("route_from_to", "")
        stops = cfg.get("stops", {})
        stops_line = ", ".join(f"{bus} — {n} ост." for bus, n in stops.items())
        header = f"{title}\n{route}\n{stops_line}\n\n"
        text = header + text + "\n\n" + t(lang, "buses.footer_campus")

    # Удаляем «Загружаю расписание...» и отправляем результат
    try:
        await context.bot.delete_message(chat_id, loading_msg.message_id)
    except BadRequest:
        pass
    await context.bot.send_message(
        chat_id,
        text,
        reply_markup=buses_keyboard(lang),
    )
