# -*- coding: utf-8 -*-
"""
Функция получения расписания группы на выбранный день или рабочие дни корпуса.
API: POST https://api.mgkeit.space/api/v1/timetable
Поддержка кэширования по ETag (If-None-Match → 304 Not Modified).
"""

import os
from typing import Literal, Optional, Union

import httpx

BASE_URL = "https://api.mgkeit.space"

WeekType = Literal["current", "even", "odd"]


def get_timetable(
    group: str,
    building: Optional[str] = None,
    week: WeekType = "current",
    day: Optional[int] = None,
    etag: Optional[str] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """
    Возвращает расписание группы на выбранный день или на рабочие дни корпуса.

    Args:
        group: Название группы, например 1ОЗИП-1-11-25 (ОЗФ) или 1КС-1-11-25.
        building: Название корпуса. Если не указан — выбирается автоматически.
        week: Неделя: "current" (текущая), "even" (чётная), "odd" (нечётная). По умолчанию "current".
        day: День недели: 0 Пн, 1 Вт, 2 Ср, 3 Чт, 4 Пт, 5 Сб. Если не указан — только разрешённые дни корпуса.
        etag: ETag из предыдущего ответа для условного запроса (304).

    Returns:
        (data, new_etag): при 200 — словарь {meta, data} с расписанием и ETag;
        (None, etag): при 304 — данные не изменились.
    """
    token = os.getenv("SCHEDULE_API_TOKEN")
    if not token:
        raise ValueError("SCHEDULE_API_TOKEN не задан в окружении")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if etag:
        headers["If-None-Match"] = etag

    body: dict[str, Union[str, int, None]] = {"group": group, "week": week}
    if building is not None:
        body["building"] = building
    if day is not None:
        body["day"] = day

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/timetable",
            json=body,
            headers=headers,
        )

    if resp.status_code == 304:
        return (None, etag)

    resp.raise_for_status()
    data = resp.json()
    new_etag = resp.headers.get("ETag")
    return (data, new_etag)
