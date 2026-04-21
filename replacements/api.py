# -*- coding: utf-8 -*-
"""
Функция получения замен расписания группы на указанную дату.
API: POST https://api.mgkeit.space/api/v1/replacements
Тело: {"date": "YYYY-MM-DD"}, опционально: building, group.
Использует тот же токен, что и расписание (SCHEDULE_API_TOKEN).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import SCHEDULE_API_TOKEN, REPLACEMENTS_API_TIMEOUT, SCHEDULE_TIMEZONE

BASE_URL = "https://api.mgkeit.space"
logger = logging.getLogger(__name__)


# Символы, похожие на дефис (API может вернуть Unicode minus/en-dash вместо ASCII)
_GROUP_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2212\uFE58\uFE63\uFF0D"


def _normalize_group_for_compare(s: str) -> str:
    """Нормализует строку группы для сравнения: один тип дефиса, без учёта регистра."""
    if not s:
        return ""
    s = s.strip().lower()
    for c in _GROUP_DASH_CHARS:
        s = s.replace(c, "-")
    return s


def _day_to_date(day: int) -> str:
    """Преобразует день недели 0–5 (Пн–Сб) в дату YYYY-MM-DD в текущей неделе по Москве (API в МСК)."""
    now = datetime.now(SCHEDULE_TIMEZONE)
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    target = monday + timedelta(days=day)
    return target.strftime("%Y-%m-%d")


def get_replacements(
    group: str,
    day: int,
    building: Optional[str] = None,
) -> list[dict]:
    """
    Возвращает список замен для группы на выбранный день.

    Args:
        group: Название группы, например 1ИП-3-25.
        day: День недели: 0 Пн … 5 Сб.
        building: Фильтр по корпусу (опционально).

    Returns:
        Список замен. Каждая: group, lessons, teacher_from, teacher_to,
        room_schedule, room_replace. При ошибке — [].
    """
    if not SCHEDULE_API_TOKEN:
        return []

    date_str = _day_to_date(day)
    headers = {
        "Authorization": f"Bearer {SCHEDULE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    body: dict = {"date": date_str, "group": group}
    if building:
        body["building"] = building

    try:
        with httpx.Client(timeout=REPLACEMENTS_API_TIMEOUT) as client:
            resp = client.post(
                f"{BASE_URL}/api/v1/replacements",
                json=body,
                headers=headers,
            )
    except Exception as e:
        logger.warning("replacements request failed: %s", e)
        return []

    if resp.status_code not in (200, 304):
        # 404 «замены на дату не найдены» — нормальная ситуация, не пугаем WARNING
        if resp.status_code == 404 and "не найдены" in (resp.text or ""):
            logger.debug("replacements API 404: замен на дату нет")
        else:
            logger.warning("replacements API status %s body: %s", resp.status_code, resp.text[:500])
        return []

    if resp.status_code == 304:
        logger.debug("replacements API 304 Not Modified")
        return []  # Нет тела ответа, кэш не храним — показываем «Нет замен»

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("replacements API invalid JSON: %s", e)
        return []

    # Поддержка разных ключей: items, replacements, data; массив в корне; вложенные data/result
    def _find_list(obj):
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("items", "replacements", "data"):
                val = obj.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict):
                    found = _find_list(val)
                    if found is not None:
                        return found
        return None

    raw_list = _find_list(data)
    if not isinstance(raw_list, list):
        logger.info(
            "replacements API: ответ 200, но список замен не найден. keys=%s",
            list(data.keys()) if isinstance(data, dict) else "response is not dict",
        )
        return []
    if len(raw_list) == 0:
        logger.debug(
            "replacements API: дата=%s, ответ 200, data пуст (API вернул count=0 или []).",
            date_str,
        )

    # Сравнение группы без учёта регистра и типа дефиса (API может вернуть 1ип−3−25 вместо 1ИП-3-25)
    group_norm = _normalize_group_for_compare(group or "")

    result = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        lessons = item.get("lessons") or item.get("lesson_numbers") or item.get("lesson") or []
        if isinstance(lessons, (int, float)):
            lessons = [int(lessons)]
        elif not isinstance(lessons, list):
            lessons = []
        room_replace_raw = item.get("room_replace") or item.get("room_to") or item.get("new_room")
        entry = {
            "group": str(item.get("group") or "").strip(),
            "lessons": lessons,
            "teacher_from": str(item.get("teacher_from") or item.get("teacher_from_name") or "").strip(),
            "teacher_to": str(item.get("teacher_to") or item.get("teacher_to_name") or "").strip(),
            "room_schedule": str(item.get("room_schedule") or item.get("room") or "").strip(),
            "room_replace": str(room_replace_raw).strip() if room_replace_raw is not None else "",
        }
        # Показываем только замены для запрошенной группы (если API вернул все группы)
        if group_norm and entry["group"]:
            if _normalize_group_for_compare(entry["group"]) != group_norm:
                continue
        result.append(entry)

    logger.info(
        "replacements API: date=%s group=%s → raw=%s, after filter=%s",
        date_str, group, len(raw_list), len(result),
    )
    return result
