# -*- coding: utf-8 -*-
"""Клавиатуры бота (Reply и Inline)."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from i18n import t


def main_menu_keyboard(lang: str = 'ru') -> ReplyKeyboardMarkup:
    """Клавиатура главного меню под полем ввода."""
    keys = [
        [KeyboardButton(t(lang, "menu.schedule")), KeyboardButton(t(lang, "menu.buses"))],
        [KeyboardButton(t(lang, "menu.cancel"))],
    ]
    return ReplyKeyboardMarkup(
        keys,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=t(lang, "menu.main").split('\n')[0][:50],
    )


def main_menu_inline_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Инлайн-кнопки под сообщением: Расписание, Уведомления, Автобусы, Настройки."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "menu.schedule"), callback_data="main:sched"),
            InlineKeyboardButton(t(lang, "menu.notifications"), callback_data="main:notif"),
        ],
        [
            InlineKeyboardButton(t(lang, "menu.buses"), callback_data="main:buses"),
            InlineKeyboardButton(t(lang, "menu.settings"), callback_data="main:settings"),
        ],
    ])


def schedule_day_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Инлайн-кнопки выбора дня недели для расписания + «Назад» в главный экран."""
    today_btn = InlineKeyboardButton(t(lang, "menu.today"), callback_data="sched:today")
    row1 = [
        InlineKeyboardButton(t(lang, "buttons.monday"), callback_data="sched:0"),
        InlineKeyboardButton(t(lang, "buttons.tuesday"), callback_data="sched:1"),
        InlineKeyboardButton(t(lang, "buttons.wednesday"), callback_data="sched:2"),
    ]
    row2 = [
        InlineKeyboardButton(t(lang, "buttons.thursday"), callback_data="sched:3"),
        InlineKeyboardButton(t(lang, "buttons.friday"), callback_data="sched:4"),
        InlineKeyboardButton(t(lang, "buttons.saturday"), callback_data="sched:5"),
    ]
    back_btn = InlineKeyboardButton(t(lang, "menu.back"), callback_data="back:main")
    return InlineKeyboardMarkup([[today_btn], row1, row2, [back_btn]])


def buses_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Кнопки выбора направления: К колледжу, К метро."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "buses.to_college"), callback_data="buses:home_office"),
            InlineKeyboardButton(t(lang, "buses.to_metro"), callback_data="buses:office_home"),
        ],
        [InlineKeyboardButton(t(lang, "menu.back"), callback_data="back:main")],
    ])


def schedule_back_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Кнопка «Назад» под сообщением с расписанием — возврат к выбору дня."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "menu.back"), callback_data="back:day_picker")],
    ])


def buildings_keyboard(buildings_list: list[str], lang: str = 'ru') -> InlineKeyboardMarkup:
    """Инлайн-кнопки выбора корпуса из списка API (по 1 в ряд)."""
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"building:{name}")]
        for name in buildings_list
    ]
    return InlineKeyboardMarkup(buttons)


def group_back_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Кнопка «Назад» под сообщением «В какой группе ты учишься» — возврат к выбору корпуса."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "menu.back"), callback_data="back:building")],
    ])


def settings_keyboard(lang: str = 'ru') -> InlineKeyboardMarkup:
    """Меню настроек: язык, корпус, группа, уведомления (интервал внутри уведомлений)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "settings_menu.language"), callback_data="settings:language")],
        [
            InlineKeyboardButton(t(lang, "settings_menu.building"), callback_data="settings:building"),
            InlineKeyboardButton(t(lang, "settings_menu.group"), callback_data="settings:group"),
        ],
        [InlineKeyboardButton(t(lang, "settings_menu.notifications"), callback_data="settings:notifications")],
        [InlineKeyboardButton(t(lang, "menu.back"), callback_data="back:main")],
    ])


def notifications_submenu_keyboard(
    lang: str, enabled: bool, from_main: bool
) -> InlineKeyboardMarkup:
    """Подменю уведомлений: интервал (5/10/15/30 мин), вкл/выкл, назад (в главное или в настройки)."""
    suffix = "main" if from_main else "settings"
    back_data = "back:main" if from_main else "back:settings"
    options = [5, 10, 15, 30]
    row_interval = [
        InlineKeyboardButton(
            f"{m} мин" if lang == "ru" else f"{m} min",
            callback_data=f"notif:interval:{m}:{suffix}",
        )
        for m in options
    ]
    toggle_text = t(lang, "notifications.turn_off") if enabled else t(lang, "notifications.turn_on")
    toggle_data = f"notif:toggle:{suffix}"
    return InlineKeyboardMarkup([
        row_interval,
        [InlineKeyboardButton(toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton(t(lang, "menu.back"), callback_data=back_data)],
    ])


def language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка."""
    from i18n import SUPPORTED_LANGUAGES

    buttons = [
        [
            InlineKeyboardButton("Русский 🇷🇺", callback_data="lang:ru"),
            InlineKeyboardButton("English 🇬🇧", callback_data="lang:en"),
        ],
        [
            InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang:de"),
            InlineKeyboardButton("Norsk 🇳🇴", callback_data="lang:no"),
        ],
        [
            InlineKeyboardButton("Svenska 🇸🇪", callback_data="lang:sv"),
            InlineKeyboardButton("Suomi 🇫🇮", callback_data="lang:fi"),
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="back:settings")],
    ]
    return InlineKeyboardMarkup(buttons)
