# StudentBuddy

[English](README.md) · [Русский](README.ru.md)

A Telegram bot for students: **class schedule**, **teacher substitutions**, **reminders before classes** and **bus schedules** — all in one chat. The bot's own interface supports Russian, English, German, Norwegian, Swedish and Finnish.

## Features

- **Onboarding** — after `/start`, the user picks their campus and group; the group format is validated against the schedule API.
- **Schedule** — the `/schedule` command or a menu button shows the day's classes, with substitutions for the selected day where needed.
- **Reminders** — a message sent ahead of time (by default ~10 minutes before class) with the subject, room and teacher; can be turned off in settings.
- **Buses** — directions such as "to the campus" / "to the metro" (route parsing; some scenarios need Playwright/Chromium or a configured Selenium — see [docs/README.md](docs/README.md)).
- **Settings** — interface language (**ru**, **en**, **de**, **no**, **sv**, **fi**), changing campus and group, enabling and disabling notifications.

User data is stored in **SQLite**; the database file and persistence are created when the bot runs (paths are set in `.env`).

## Tech Stack

- **Python 3.10+**, [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (polling).
- **httpx** as the HTTP client for the schedule and substitutions API.
- Optional **Redis** for a shared schedule cache between processes (see `.env.example`).

## Getting Started

```bash
git clone https://github.com/CraftStick/StudentBuddy.git
cd StudentBuddy
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

In `.env`, make sure to set **`BOT_TOKEN`** (from [@BotFather](https://t.me/BotFather)) and **`SCHEDULE_API_TOKEN`** (the schedule API token). Then:

```bash
python3 health_check.py
python3 bot.py
```

For more detail — installation, Docker, deployment and environment variables — see **[docs/README.md](docs/README.md)** (in Russian).
