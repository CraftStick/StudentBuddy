# -*- coding: utf-8 -*-
"""Обработчики меню «Автобусы» — красивые ссылки на Яндекс.Карты без парсера."""

import html
import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from utils.user_helpers import get_user_language
from i18n import t
from keyboards import buses_keyboard

logger = logging.getLogger(__name__)

# К колледжу — остановка «Метро Коломенская»
TO_COLLEGE = {
    "url": "https://yandex.ru/maps/213/moscow/stops/stop__9643158/?ll=37.663089%2C55.676860&tab=overview&z=18",
    "message": "Метро Коломенская · 3A",
    "buses": ["м19", "с820"],
    "route_from_to": "От метро Коломенская до Электромеханический колледж",
    "stops": {"м19": 5, "с820": 5},
}

# К метро — остановка «Коломенский проезд, 8». overview как у «К колледжу» — панель маршрутов грузится стабильнее, чем на tab=schedule.
TO_METRO = {
    "url": "https://yandex.ru/maps/213/moscow/stops/stop__9645789/?ll=37.648561%2C55.665797&tab=timetable&z=20",
    "message": "Коломенский проезд, 8",
    "buses": ["с820"],
    "route_from_to": "От Коломенский проезд, 8 до метро Коломенская",
    "stops": {"с820": 4},
    "extra_wait_sec": 5,
    "bus_aliases": {"с820": ["820"]},
    "wait_timeout_ms": 90000,
}

BUS_DIRECTIONS = {
    "home_office": TO_COLLEGE,
    "office_home": TO_METRO,
}

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
    """По нажатию «К колледжу» или «К метро» — отправляем оформленное сообщение и ссылку на Я.Карты."""
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

    cfg = BUS_DIRECTIONS.get(direction, {})

    url = cfg.get("url", "")
    link_html = f'<a href="{html.escape(url)}">Посмотреть на Я.Картах</a>' if url else ""

    # Красивое статичное сообщение с описанием маршрута и ссылкой на карты
    is_to_college = direction == "home_office"
    title = ("🎓 " + t(lang, "buses.to_college")) if is_to_college else ("🚇 " + t(lang, "buses.to_metro"))
    route = cfg.get("route_from_to", "")
    stops = cfg.get("stops", {})
    stops_lines: list[str] = []
    for bus, n in stops.items():
        if is_to_college:
            stops_lines.append(f"  • {bus} — {n} ост. до колледжа")
        else:
            stops_lines.append(f"  • {bus} — {n} ост. до метро")

    parts = [
        html.escape(title),
        "",
        "🚶‍♂️ " + html.escape(route),
        "",
        "🚌 Остановки:",
        *[html.escape(s) for s in stops_lines],
        "",
        "⏱️ Актуальное время прибытия автобусов смотрите в Яндекс.Картах по ссылке ниже.",
        "",
    ]
    if link_html:
        parts.append(link_html)
    text = "\n".join(parts)
    parse_mode = "HTML"
    await context.bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=buses_keyboard(lang))
