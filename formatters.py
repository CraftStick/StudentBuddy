# -*- coding: utf-8 -*-
"""Форматирование расписания и замен для сообщений бота."""

from config import NUMBER_EMOJI, SUBJECT_EMOJI
from i18n import t


def subject_emoji(subject: str) -> str:
    """Подбирает эмодзи для предмета по ключевым словам."""
    if not subject:
        return "📌"
    s = subject.lower()
    for key, emoji in SUBJECT_EMOJI.items():
        if key in s:
            return emoji
    return "📌"


def week_label(meta: dict, lang: str = 'ru') -> str:
    """Текст недели: Чётная (even) / Нечётная (odd) / Текущая."""
    week_type = (meta.get("week_type") or "").lower()
    if week_type == "even":
        return t(lang, "schedule.week_even")
    if week_type == "odd":
        return t(lang, "schedule.week_odd")
    num = meta.get("current_week") or meta.get("week")
    if num is not None:
        try:
            n = int(num)
            return t(lang, "schedule.week_even") if n % 2 == 0 else t(lang, "schedule.week_odd")
        except (TypeError, ValueError):
            pass
    return str(meta.get("current_week", meta.get("week", "?")))


def format_timetable(data: dict, lang: str = 'ru') -> str:
    """Форматирует ответ API в читабельный вид с эмодзи."""
    meta = data.get("meta", {})
    group = (meta.get("group") or "?").strip()
    building = (meta.get("building") or "?").strip()
    week_label_str = week_label(meta, lang)

    parts = [
        f"{t(lang, 'schedule.header_group')} {group}",
        t(lang, "schedule.header_building", building=building),
        f"{t(lang, 'schedule.header_week')} {week_label_str}",
        "",
    ]

    for day_block in data.get("data", []):
        day_name = (day_block.get("day_name") or "?").strip()
        units = day_block.get("units", [])
        if not units:
            continue
        parts.append(f"🔻 {day_name}")
        parts.append("")

        for i, u in enumerate(units):
            num_emoji = NUMBER_EMOJI[i] if i < len(NUMBER_EMOJI) else f"{i + 1}."
            subj = (u.get("subject") or "—").strip()
            start = (u.get("start") or "").strip()
            end = (u.get("end") or "").strip()
            
            # Костыль: API возвращает неправильное время для субботы (8:30 вместо 9:00)
            if day_name.lower() == "суббота" and start == "8:30":
                start = "9:00"
                # Если конец тоже нужно сдвинуть (8:30-9:15 -> 9:00-9:45)
                if end == "9:15":
                    end = "9:45"
            teacher = (u.get("teacher") or "").strip()
            room = (u.get("room") or "").strip()

            time_range = f"{start} – {end}" if start and end else ""
            subj_emoji = subject_emoji(subj)
            line1 = f"{num_emoji} {time_range} | {subj_emoji} {subj}" if time_range else f"{num_emoji} {subj_emoji} {subj}"
            parts.append(line1)
            if teacher:
                parts.append(t(lang, "schedule.teacher", teacher=teacher))
            if room:
                parts.append(t(lang, "schedule.room", room=room))
            parts.append("")

        parts.append("")

    text = "\n".join(parts).rstrip()
    return text or t(lang, "schedule.no_data")


def format_replacements(replacements: list[dict], lang: str = 'ru') -> str:
    """Форматирует список замен по структуре API."""
    if not replacements:
        return t(lang, "schedule.no_replacements")
    parts = [t(lang, "schedule.replacements")]
    for r in replacements:
        lessons = r.get("lessons") or []
        sorted_lessons = sorted(lessons)
        if len(sorted_lessons) == 1:
            lesson_str = f"{sorted_lessons[0]} {t(lang, 'schedule.lesson')}"
        elif sorted_lessons:
            lesson_str = ", ".join(str(x) for x in sorted_lessons) + f" {t(lang, 'schedule.lesson')}"
        else:
            lesson_str = "?"
        teacher_from = (r.get("teacher_from") or "").strip()
        teacher_to = (r.get("teacher_to") or "").strip()
        room_schedule = (r.get("room_schedule") or "").strip()
        room_replace = r.get("room_replace")
        room_replace_str = str(room_replace).strip() if room_replace else ""
        num_emoji = NUMBER_EMOJI[sorted_lessons[0] - 1] if sorted_lessons and 1 <= sorted_lessons[0] <= len(NUMBER_EMOJI) else "•"
        parts.append("")
        parts.append(f"{num_emoji} {lesson_str}")
        if teacher_from or teacher_to:
            if teacher_from and teacher_to:
                parts.append(f"   {t(lang, 'schedule.instead_of', **{'from': teacher_from, 'to': teacher_to})}")
            elif teacher_to:
                parts.append(f"   {t(lang, 'schedule.teacher', teacher=teacher_to)}")
            else:
                parts.append(f"   {t(lang, 'schedule.was', teacher=teacher_from)}")
        if room_schedule or room_replace_str:
            if room_replace_str:
                parts.append(f"   {t(lang, 'schedule.room', room=room_schedule)} → {room_replace_str}")
            else:
                parts.append(f"   {t(lang, 'schedule.room', room=room_schedule)}")
    return "\n".join(parts)
