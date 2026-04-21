# StudentBuddy

Telegram-бот для студентов: **расписание**, **замены преподавателей**, **напоминания перед парами** и **расписание автобусов** — в одном чате.

## Что умеет бот

- **Онбординг** — после `/start` выбирается корпус и группа; формат группы проверяется через API расписания.
- **Расписание** — команда `/schedule` или кнопка в меню: день недели, пары, при необходимости замены на выбранный день.
- **Напоминания** — заранее (по умолчанию за ~10 минут до начала пары) сообщение с предметом, аудиторией и преподавателем; можно отключить в настройках.
- **Автобусы** — направления вроде «к учебному корпусу» / «к метро» (парсинг маршрутов; для части сценариев нужны Playwright/Chromium или настроенный Selenium — см. [docs/README.md](docs/README.md)).
- **Настройки** — язык интерфейса (**ru**, **en**, **de**, **no**, **sv**, **fi**), смена корпуса и группы, включение и выключение уведомлений.

Данные пользователей хранятся в **SQLite**; файл БД и persistence создаются при работе бота (пути задаются в `.env`).

## Технологии

- **Python 3.10+**, [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) (polling).
- HTTP-клиент **httpx** для API расписания и замен.
- Опционально **Redis** для общего кэша расписания между процессами (см. `.env.example`).

## Быстрый старт

```bash
git clone https://github.com/CraftStick/StudentBuddy.git
cd StudentBuddy
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` обязательно укажи **`BOT_TOKEN`** (от [@BotFather](https://t.me/BotFather)) и **`SCHEDULE_API_TOKEN`** (токен API расписания). Затем:

```bash
python3 health_check.py
python3 bot.py
```

Подробнее: установка, Docker, деплой и переменные окружения — **[docs/README.md](docs/README.md)**. Команды выката на сервер — **[docs/DEPLOY.md](docs/DEPLOY.md)**. История изменений — **[docs/CHANGELOG.md](docs/CHANGELOG.md)**.