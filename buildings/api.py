# -*- coding: utf-8 -*-
"""
Получение списка корпусов.
API: POST https://api.mgkeit.space/api/v1/buildings
Поддержка кэширования по ETag (If-None-Match → 304 Not Modified).
"""

import os
from typing import Optional

import httpx

BASE_URL = "https://api.mgkeit.space"


def get_buildings(etag: Optional[str] = None) -> tuple[Optional[list[str]], Optional[str]]:
    """
    Возвращает список всех корпусов.

    Аутентификация: Authorization: Bearer <SCHEDULE_API_TOKEN>.
    Кэш: передайте ETag в If-None-Match — при отсутствии изменений сервер вернёт 304.

    Args:
        etag: ETag из предыдущего ответа для условного запроса (304).

    Returns:
        (buildings, new_etag): при 200 — список названий корпусов и ETag;
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

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{BASE_URL}/api/v1/buildings",
            json={},
            headers=headers,
        )

    if resp.status_code == 304:
        return (None, etag)

    resp.raise_for_status()
    data = resp.json()
    buildings = data.get("buildings") or []
    new_etag = resp.headers.get("ETag")
    return (buildings, new_etag)
