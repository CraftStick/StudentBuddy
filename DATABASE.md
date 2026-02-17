# База данных StudentBuddy

## Описание

Бот использует SQLite3 для хранения данных пользователей. База данных автоматически создается при первом запуске бота.

## Структура таблиц

### Таблица `users`

Хранит информацию о пользователях бота.

| Поле | Тип | Описание |
|------|-----|----------|
| `user_id` | INTEGER PRIMARY KEY | ID пользователя в Telegram (уникальный) |
| `username` | TEXT | Username пользователя в Telegram (может быть NULL) |
| `first_name` | TEXT | Имя пользователя в Telegram (может быть NULL) |
| `name` | TEXT | Отображаемое имя для приветствия |
| `building` | TEXT | Корпус, в котором учится пользователь |
| `student_group` | TEXT | Номер группы пользователя (например, "1ИП-3-25") |
| `notifications_enabled` | INTEGER | 1 - уведомления включены, 0 - выключены (по умолчанию 1) |
| `created_at` | TEXT | Дата и время создания записи (ISO формат) |
| `updated_at` | TEXT | Дата и время последнего обновления (ISO формат) |

## API базы данных

Модуль `database.py` предоставляет класс `Database` со следующими методами:

### Основные методы

#### `__init__(db_path: str = "studentbuddy.db")`
Инициализирует базу данных и создает таблицы, если их нет.

```python
from database import Database
db = Database()  # Использует файл studentbuddy.db
```

#### `add_user(user_id, username=None, first_name=None, name=None) -> bool`
Добавляет нового пользователя в базу данных.

```python
db.add_user(
    user_id=123456789,
    username="john_doe",
    first_name="John",
    name="Джон"
)
```

#### `get_user(user_id) -> Optional[Dict[str, Any]]`
Получает данные пользователя по ID.

```python
user = db.get_user(123456789)
if user:
    print(f"Группа: {user['student_group']}")
    print(f"Корпус: {user['building']}")
```

#### `update_user(user_id, **kwargs) -> bool`
Обновляет данные пользователя. Можно передать любые поля: `building`, `student_group`, `notifications_enabled`, `name`, `username`, `first_name`.

```python
# Обновление группы
db.update_user(123456789, student_group="2ИП-1-26")

# Обновление нескольких полей сразу
db.update_user(
    123456789,
    building="Судостроительная",
    student_group="2ИП-1-26"
)
```

#### `delete_user(user_id) -> bool`
Удаляет пользователя из базы данных.

```python
db.delete_user(123456789)
```

#### `user_exists(user_id) -> bool`
Проверяет, существует ли пользователь в базе данных.

```python
if db.user_exists(123456789):
    print("Пользователь найден")
```

### Методы для работы с уведомлениями

#### `set_notifications(user_id, enabled: bool) -> bool`
Включает или отключает уведомления для пользователя.

```python
# Включить уведомления
db.set_notifications(123456789, True)

# Отключить уведомления
db.set_notifications(123456789, False)
```

#### `get_users_with_notifications() -> list[Dict[str, Any]]`
Получает список всех пользователей с включенными уведомлениями, у которых указаны корпус и группа.

```python
users = db.get_users_with_notifications()
for user in users:
    print(f"User {user['user_id']}: {user['student_group']}")
```

### Вспомогательные методы

#### `get_all_users() -> list[Dict[str, Any]]`
Получает список всех пользователей.

```python
all_users = db.get_all_users()
print(f"Всего пользователей: {len(all_users)}")
```

## Миграция данных

Если у вас уже есть данные в pickle-файле (`studentbuddy_data.pickle`), вы можете мигрировать их в SQLite:

```bash
python3 migrate_to_db.py
```

Скрипт:
- Прочитает данные из pickle-файла
- Создаст или обновит записи в SQLite
- Выведет статистику миграции

## Примеры использования

### Регистрация нового пользователя

```python
from database import Database

db = Database()

# При команде /start
user_id = update.effective_user.id
username = update.effective_user.username
first_name = update.effective_user.first_name

if not db.user_exists(user_id):
    db.add_user(user_id, username, first_name, first_name)
```

### Сохранение выбранной группы

```python
# После выбора корпуса и группы
db.update_user(
    user_id,
    building="Судостроительная",
    student_group="1ИП-3-25"
)
```

### Изменение группы (пользователь ошибся)

```python
# Пользователь может в любой момент снова пройти /start
# или нажать кнопку "Изменить данные"
db.update_user(user_id, student_group="1ИП-4-25")
```

### Получение данных для расписания

```python
user = db.get_user(user_id)
if user:
    group = user['student_group']
    building = user['building']
    # Запросить расписание для этой группы
```

### Управление уведомлениями

```python
# Включить уведомления
db.set_notifications(user_id, True)

# Отключить уведомления
db.set_notifications(user_id, False)

# Получить всех пользователей для рассылки напоминаний
users = db.get_users_with_notifications()
for user in users:
    # Отправить напоминание
    pass
```

## Резервное копирование

Файл базы данных `studentbuddy.db` - это обычный SQLite файл. Для резервного копирования просто скопируйте его:

```bash
cp studentbuddy.db studentbuddy_backup_$(date +%Y%m%d).db
```

## Восстановление

Для восстановления из резервной копии:

```bash
cp studentbuddy_backup_20260209.db studentbuddy.db
```

## Просмотр данных

Вы можете просматривать и редактировать данные с помощью любого SQLite клиента:

```bash
# Консольный клиент
sqlite3 studentbuddy.db

# Примеры SQL запросов:
SELECT * FROM users;
SELECT COUNT(*) FROM users WHERE notifications_enabled = 1;
SELECT student_group, COUNT(*) FROM users GROUP BY student_group;
```

## Безопасность

- База данных хранится локально на сервере
- Файл `studentbuddy.db` добавлен в `.gitignore` и не попадает в репозиторий
- Все операции с БД используют параметризованные запросы (защита от SQL injection)
- Контекстный менеджер автоматически откатывает транзакции при ошибках

## Производительность

- SQLite отлично справляется с нагрузкой до нескольких тысяч пользователей
- Все запросы к БД неблокирующие (используют контекстные менеджеры)
- Индексы создаются автоматически для PRIMARY KEY
- Для больших нагрузок рекомендуется миграция на PostgreSQL или MySQL
