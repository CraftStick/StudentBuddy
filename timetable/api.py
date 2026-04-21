# -*- coding: utf-8 -*-
"""
Функция получения расписания группы на выбранный день или рабочие дни корпуса.
API: POST https://api.mgkeit.space/api/v1/timetable
Поддержка кэширования по ETag (If-None-Match → 304 Not Modified).
Request coalescing: один запрос к API на ключ (группа + дата), остальные ждут результат.
"""

from typing import Literal, Optional, Union

import httpx

from cache_manager import cache_manager
from config import SCHEDULE_API_TOKEN, SCHEDULE_API_TIMEOUT, schedule_coalescer

BASE_URL = "https://api.mgkeit.space"

WeekType = Literal["current", "even", "odd"]


def _schedule_coalescer_key(
    group: str,
    building: Optional[str],
    week: WeekType,
    day: Optional[int],
) -> str:
    """Ключ для coalescer: schedule:{группа}:{дата} (разные группы и даты кэшируются отдельно)."""
    date_part = f"{building or ''}:{week}:{day if day is not None else 'all'}"
    return f"schedule:{group}:{date_part}"


def _fetch_timetable_once(
    group: str,
    building: Optional[str],
    week: WeekType,
    day: Optional[int],
) -> tuple[Optional[dict], Optional[str]]:
    """
    Один запрос к API расписания (вызывается под coalescer).
    Использует cache_manager для ETag. Возвращает (data, etag).
    """
    cache_key = cache_manager.get_cache_key("timetable", group, building, week, day)
    etag = cache_manager.get_etag(cache_key)

    headers = {
        "Authorization": f"Bearer {SCHEDULE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    if etag:
        headers["If-None-Match"] = etag

    body: dict[str, Union[str, int, None]] = {"group": group, "week": week}
    if building is not None:
        body["building"] = building
    if day is not None:
        body["day"] = day

    with httpx.Client(timeout=SCHEDULE_API_TIMEOUT) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/timetable",
            json=body,
            headers=headers,
        )

    if resp.status_code == 304:
        cached_data = cache_manager.get_data(cache_key)
        if cached_data:
            return (cached_data, etag)
        return (None, etag)

    resp.raise_for_status()
    data = resp.json()
    new_etag = resp.headers.get("ETag")
    cache_manager.set(cache_key, data, new_etag, ttl=300)
    return (data, new_etag)


async def get_timetable(
    group: str,
    building: Optional[str] = None,
    week: WeekType = "current",
    day: Optional[int] = None,
    etag: Optional[str] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """
    Возвращает расписание группы на выбранный день или на рабочие дни корпуса.
    Запросы с одинаковым ключом (группа + дата) схлопываются в один вызов API.

    Args:
        group: Название группы, например 1ОЗИП-1-11-25 (ОЗФ) или 1КС-1-11-25.
        building: Название корпуса. Если не указан — выбирается автоматически.
        week: Неделя: "current" (текущая), "even" (чётная), "odd" (нечётная). По умолчанию "current".
        day: День недели: 0 Пн, 1 Вт, 2 Ср, 3 Чт, 4 Пт, 5 Сб. Если не указан — только разрешённые дни корпуса.
        etag: Не используется (оставлен для совместимости; ETag берётся из cache_manager).

    Returns:
        (data, new_etag): при 200 — словарь {meta, data} с расписанием и ETag;
        (None, etag): при 304 — данные не изменились.
    """
    if not SCHEDULE_API_TOKEN:
        raise ValueError("SCHEDULE_API_TOKEN не задан в окружении")

    key = _schedule_coalescer_key(group, building, week, day)
    return await schedule_coalescer.get(
        key,
        lambda: _fetch_timetable_once(group, building, week, day),
    )
