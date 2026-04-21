# StudentBuddy Bot

Telegram-бот для студентов: расписание занятий, замены, уведомления за 10 минут до урока и расписание автобусов (Яндекс.Карты / mosgortrans).

## Описание

- **Регистрация:** выбор корпуса и группы (проверка через API расписания).
- **Расписание:** команда `/schedule` или кнопка «📅 Расписание», выбор дня; показ замен.
- **Уведомления:** напоминания за ~10 минут до начала урока (при включённых уведомлениях).
- **Автобусы:** расписание «К колледжу» / «К метро» (парсер mosgortrans, опционально Selenium/Firefox).
- **Настройки:** язык (ru, en, de, no, sv, fi), смена корпуса/группы, вкл/выкл уведомлений.

Данные пользователей хранятся в SQLite. При первом запуске база и таблицы создаются автоматически.

## Установка

```bash
git clone <repo>
cd StudentBuddy
pip install -r requirements.txt
```

Рекомендуется использовать виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# или: .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Настройка

1. Скопируйте шаблон переменных окружения:

   ```bash
   cp .env.example .env
   ```

2. Отредактируйте `.env` и задайте обязательные переменные:

   | Переменная             | Описание                          |
   |------------------------|-----------------------------------|
   | `BOT_TOKEN`            | Токен бота от @BotFather          |
   | `SCHEDULE_API_TOKEN`   | Токен API расписания (mgkeit.space) |

   Опционально:

   | Переменная        | По умолчанию                   | Описание                    |
   |-------------------|--------------------------------|-----------------------------|
   | `DATABASE_PATH`   | `studentbuddy.db`              | Путь к файлу SQLite         |
   | `PERSISTENCE_FILE`| `data/studentbuddy_data.pickle`| Файл persistence            |
   | `LOG_LEVEL`       | `INFO`                         | Уровень логирования         |

3. Проверка перед запуском:

   ```bash
   python3 health_check.py
   ```

## Запуск

**Локально (polling):**

```bash
python3 bot.py
```

Логи пишутся в консоль и в файл `logs/bot.log`.

**На сервере (systemd):**

- Используйте `studentbuddy.service` из репозитория (при необходимости скорректируйте пути и пользователя).
- После деплоя убедитесь, что в `.env` заданы `BOT_TOKEN` и `SCHEDULE_API_TOKEN`, затем выполните `health_check.py` и запустите сервис.

Остановка по Ctrl+C или SIGTERM выполняется корректно (graceful shutdown).

## Деплой на сервер

### Что установить на сервере

1. **ОС и Python**
   - Linux (Ubuntu 22.04 / Debian 12 или аналог).
   - Python 3.10+:
     ```bash
     sudo apt update && sudo apt install -y python3 python3-venv python3-pip
     ```

2. **PM2** (запуск и автозапуск бота):
   ```bash
   sudo npm install -g pm2
   pm2 startup   # автозапуск после перезагрузки (команду выполнить как указано в выводе)
   ```

3. **Опционально: меню «Автобусы»**
   - **Вариант A — локальный Firefox:** установить Firefox и GeckoDriver:
     ```bash
     sudo apt install -y firefox-esr
     # GeckoDriver: скачать с https://github.com/mozilla/geckodriver/releases
     # и положить в PATH, например: sudo mv geckodriver /usr/local/bin/
     ```
   - **Вариант B — Selenoid (Docker):** поднять Selenoid с образом Firefox (см. `parser/mosgortrans-master/docker-compose.yml` и `deploy/browsers.json`), в `.env` указать `SELENOID_URL=http://<хост>:4444/wd/hub`.
   - Без Firefox/GeckoDriver или Selenoid бот работает, но раздел «🚌 Автобусы» будет выдавать ошибку и ссылку на расписание.

4. **Каталог проекта**
   - Создать каталог на сервере (например `/root/StudentBuddy` или `/home/user/StudentBuddy`).
   - Скопировать туда код (git clone или scp/rsync).

### Как деплоить

**Способ 1 — скрипт `deploy.sh` (рекомендуется)**

На своей машине из корня репозитория:

```bash
# Настроить сервер и путь (при необходимости)
export DEPLOY_SERVER="root@ВАШ_IP"
export DEPLOY_PATH="/root/StudentBuddy"

# На сервере должны быть: SSH-доступ, установлены Python 3, venv, PM2
# В корне проекта должен быть файл .env (скопировать с .env.example и заполнить)

./deploy.sh
```

Скрипт: проверяет `.env` и синтаксис, делает бэкап БД и `.env` на сервере, копирует файлы, ставит зависимости в venv, перезапускает бота через PM2.

**Способ 2 — вручную**

На сервере в каталоге проекта:

```bash
cd /root/StudentBuddy   # или ваш путь
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Создать/отредактировать .env (BOT_TOKEN, SCHEDULE_API_TOKEN и т.д.)
python3 health_check.py
pm2 start bot.py --name student-buddy --interpreter venv/bin/python3
pm2 save
```

Дальше при обновлении кода: `git pull` (или скопировать файлы), затем `source venv/bin/activate && pip install -r requirements.txt` и `pm2 restart student-buddy`.

### Переменные окружения на сервере

В `.env` на сервере обязательно задать:

| Переменная             | Описание                    |
|------------------------|-----------------------------|
| `BOT_TOKEN`            | Токен бота от @BotFather    |
| `SCHEDULE_API_TOKEN`   | Токен API расписания        |

Остальное — по необходимости (см. `.env.example`). Для автобусов через Selenoid добавить `SELENOID_URL`.

### Проверка после деплоя

```bash
pm2 list
pm2 logs student-buddy
```

В Telegram: команда `/start`, выбор корпуса/группы, проверка расписания и (если настроено) автобусов.

## Дополнительно

- **Управление БД:** `python3 db_admin.py help` — статистика, список пользователей, резервная копия.
- **Парсер автобусов:** для работы меню «🚌 Автобусы» нужны Selenium и Firefox/GeckoDriver (или Selenoid с Firefox); без них бот работает, раздел автобусов выдаст сообщение об ошибке.

## Структура проекта

```
bot.py                 # Точка входа
config.py              # Константы и переменные окружения
database/              # Работа с SQLite
handlers/              # Обработчики команд и callback
keyboards/             # Клавиатуры (Reply, Inline)
middlewares/           # Rate limiting
utils/                 # Вспомогательные функции, форматирование
timetable/             # API расписания
replacements/          # API замен
locales/               # Файлы переводов (i18n)
docs/                  # Документация (README, CHANGELOG)
logs/                  # Логи (создаётся при запуске)
data/                  # Persistence и данные (создаётся при запуске)
```

Подробности изменений — в [CHANGELOG.md](CHANGELOG.md).
