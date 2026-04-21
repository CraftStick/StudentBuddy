# -*- coding: utf-8 -*-
"""Утилиты для работы со временем и расписанием."""


def fix_saturday_time(start_time: str, end_time: str, day_weekday: int) -> tuple[str, str]:
    """Исправляет некорректное время для субботы из API (8:30 → 9:00)."""
    if day_weekday == 5 and start_time == "8:30":
        start_time = "9:00"
        if end_time == "9:15":
            end_time = "9:45"
    return start_time, end_time
