# -*- coding: utf-8 -*-
"""
Функция получения замен расписания группы на указанную дату.
API: POST https://api.mgkeit.space/api/v1/replacements
Тело: {"date": "YYYY-MM-DD"}, опционально: building, group.
Использует тот же токен, что и расписание (SCHEDULE_API_TOKEN).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

BASE_URL = "https://api.mgkeit.space"
logger = logging.getLogger(__name__)


def _day_to_date(day: int) -> str:
    """Преобразует день недели 0–5 (Пн–Сб) в дату YYYY-MM-DD в текущей неделе."""
    now = datetime.now()
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
    token = os.getenv("SCHEDULE_API_TOKEN")
    if not token:
        return []

    date_str = _day_to_date(day)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body: dict = {"date": date_str, "group": group}
    if building:
        body["building"] = building

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{BASE_URL}/api/v1/replacements",
                json=body,
                headers=headers,
            )
    except Exception as e:
        logger.warning("replacements request failed: %s", e)
        return []

    if resp.status_code not in (200, 304):
        logger.warning("replacements API status %s body: %s", resp.status_code, resp.text[:500])
        return []

    if resp.status_code == 304:
        return []  # Нет тела ответа, кэш не храним — показываем «Нет замен»

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("replacements API invalid JSON: %s", e)
        return []

    # Поддержка разных ключей ответа: items, replacements, data
    raw_list = data.get("items") or data.get("replacements") or data.get("data")
    if not isinstance(raw_list, list):
        logger.debug("replacements API: no list in response, keys=%s", list(data.keys()))
        return []

    result = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        lessons = item.get("lessons") or item.get("lesson_numbers") or item.get("lesson") or []
        if isinstance(lessons, (int, float)):
            lessons = [int(lessons)]
        elif not isinstance(lessons, list):
            lessons = []
        entry = {
            "group": str(item.get("group") or "").strip(),
            "lessons": lessons,
            "teacher_from": str(item.get("teacher_from") or item.get("teacher_from_name") or "").strip(),
            "teacher_to": str(item.get("teacher_to") or item.get("teacher_to_name") or "").strip(),
            "room_schedule": str(item.get("room_schedule") or item.get("room") or "").strip(),
            "room_replace": item.get("room_replace"),
        }
        # Показываем только замены для запрошенной группы (если API вернул все группы)
        if group and entry["group"] and entry["group"] != group:
            continue
        result.append(entry)

    return result
