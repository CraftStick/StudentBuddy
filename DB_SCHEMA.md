# Схема базы данных StudentBuddy

## Визуализация

```
┌─────────────────────────────────────────────────────────────┐
│                      Таблица: users                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┬──────────────┬──────────────────┐    │
│  │ Поле             │ Тип          │ Ограничения      │    │
│  ├──────────────────┼──────────────┼──────────────────┤    │
│  │ user_id          │ INTEGER      │ PRIMARY KEY      │    │
│  │ username         │ TEXT         │ NULL             │    │
│  │ first_name       │ TEXT         │ NULL             │    │
│  │ name             │ TEXT         │ NULL             │    │
│  │ building         │ TEXT         │ NULL             │    │
│  │ student_group    │ TEXT         │ NULL             │    │
│  │ notifications_   │ INTEGER      │ DEFAULT 1        │    │
│  │   enabled        │              │                  │    │
│  │ created_at       │ TEXT         │ NOT NULL         │    │
│  │ updated_at       │ TEXT         │ NOT NULL         │    │
│  └──────────────────┴──────────────┴──────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Поток данных

```
┌────────────┐
│ Пользователь │
└──────┬─────┘
       │
       │ /start
       ▼
┌──────────────┐
│ Telegram Bot  │◄─── Проверка: user_exists()?
└──────┬───────┘
       │
       │ Нет → add_user()
       ▼
┌─────────────────┐
│  База данных     │
│  (SQLite3)       │
└─────────┬───────┘
          │
          │ Да → get_user()
          ▼
┌──────────────────┐
│  context.user_   │
│     data         │ ◄─── Кэширование для быстрого доступа
└──────────────────┘
```

## Жизненный цикл данных

### 1. Регистрация пользователя

```
/start
  ↓
Выбор корпуса → update_user(building="...")
  ↓
Ввод группы → update_user(student_group="...")
  ↓
Готово! Данные в БД ✅
```

### 2. Изменение данных

```
Кнопка "Изменить данные"
  ↓
Новый корпус → update_user(building="новый")
  ↓
Новая группа → update_user(student_group="новая")
  ↓
Старые данные перезаписаны ✅
```

### 3. Запрос расписания

```
/schedule или кнопка 📅
  ↓
Проверка context.user_data["group"]
  ↓
  Нет?
  ↓
get_user(user_id) → Загрузка из БД
  ↓
Кэширование в context
  ↓
Показ расписания ✅
```

### 4. Уведомления

```
JobQueue (каждую минуту)
  ↓
get_users_with_notifications()
  ↓
Для каждого пользователя:
  - Получить расписание
  - Проверить урок через 10 мин
  - Отправить уведомление ✅
```

## Пример данных

```sql
-- Пример записи в таблице users
INSERT INTO users VALUES (
    123456789,                          -- user_id
    'john_doe',                         -- username
    'Иван',                             -- first_name
    'Иван',                             -- name
    'Судостроительная',                 -- building
    '1ИП-3-25',                         -- student_group
    1,                                  -- notifications_enabled
    '2026-02-09T12:00:00.000000',      -- created_at
    '2026-02-09T12:05:30.000000'       -- updated_at
);
```

## SQL запросы

### Получить всех пользователей группы

```sql
SELECT * FROM users 
WHERE student_group = '1ИП-3-25';
```

### Пользователи с уведомлениями

```sql
SELECT * FROM users 
WHERE notifications_enabled = 1 
  AND building IS NOT NULL 
  AND student_group IS NOT NULL;
```

### Статистика по корпусам

```sql
SELECT building, COUNT(*) as count 
FROM users 
WHERE building IS NOT NULL 
GROUP BY building 
ORDER BY count DESC;
```

### Топ-10 групп

```sql
SELECT student_group, COUNT(*) as count 
FROM users 
WHERE student_group IS NOT NULL 
GROUP BY student_group 
ORDER BY count DESC 
LIMIT 10;
```

### Активность пользователей

```sql
SELECT 
    DATE(created_at) as date,
    COUNT(*) as new_users 
FROM users 
GROUP BY DATE(created_at) 
ORDER BY date DESC 
LIMIT 30;
```

## Индексы

База данных автоматически создает индекс для `user_id` (PRIMARY KEY).

Для улучшения производительности можно добавить:

```sql
-- Индекс для быстрого поиска по группе
CREATE INDEX idx_student_group ON users(student_group);

-- Индекс для фильтрации по уведомлениям
CREATE INDEX idx_notifications ON users(notifications_enabled);

-- Составной индекс для частых запросов
CREATE INDEX idx_group_building ON users(student_group, building);
```

## Миграции

### Добавление нового поля

```sql
-- Пример: добавить поле last_activity
ALTER TABLE users ADD COLUMN last_activity TEXT;

-- Обновить существующие записи
UPDATE users SET last_activity = updated_at;
```

### Изменение типа поля

SQLite не поддерживает прямое изменение типа. Нужно:

```sql
-- 1. Создать новую таблицу
CREATE TABLE users_new (
    user_id INTEGER PRIMARY KEY,
    -- новая структура
);

-- 2. Скопировать данные
INSERT INTO users_new SELECT * FROM users;

-- 3. Удалить старую таблицу
DROP TABLE users;

-- 4. Переименовать новую
ALTER TABLE users_new RENAME TO users;
```

## Резервное копирование

### Автоматическое

```bash
# Через db_admin.py
python3 db_admin.py backup
```

### Ручное

```bash
# Просто скопировать файл
cp studentbuddy.db studentbuddy_backup.db
```

### Через SQLite

```bash
# Экспорт в SQL
sqlite3 studentbuddy.db .dump > backup.sql

# Импорт из SQL
sqlite3 new_studentbuddy.db < backup.sql
```

## Ограничения SQLite

### Что работает хорошо

- ✅ До 10,000+ пользователей
- ✅ Одновременное чтение
- ✅ Простые транзакции
- ✅ Локальное хранение

### Когда нужна миграция

- ❌ >50,000 пользователей
- ❌ Много одновременных записей
- ❌ Распределенная система
- ❌ Сложная аналитика

→ Мигрируйте на PostgreSQL или MySQL

## Безопасность

### Защита от SQL Injection

```python
# ✅ Правильно (параметризованные запросы)
cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))

# ❌ Неправильно (уязвимо!)
cursor.execute(f"SELECT * FROM users WHERE user_id = {user_id}")
```

### Права доступа к файлу

```bash
# Установить права только для владельца
chmod 600 studentbuddy.db
```

### Шифрование (опционально)

Для критичных данных используйте SQLCipher:

```bash
pip install pysqlcipher3
```

## Мониторинг

### Размер базы данных

```bash
ls -lh studentbuddy.db
```

### Количество записей

```bash
sqlite3 studentbuddy.db "SELECT COUNT(*) FROM users;"
```

### Проверка целостности

```bash
sqlite3 studentbuddy.db "PRAGMA integrity_check;"
```

### Оптимизация

```bash
# Уменьшить размер файла после удалений
sqlite3 studentbuddy.db "VACUUM;"
```

## Диаграмма компонентов

```
┌─────────────────────────────────────────────────────────┐
│                    StudentBuddy Bot                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐      ┌──────────────┐                │
│  │   bot.py     │      │   handlers/  │                │
│  │              │──────│              │                │
│  └──────┬───────┘      └──────┬───────┘                │
│         │                     │                         │
│         │   ┌─────────────────┘                        │
│         │   │                                           │
│         ▼   ▼                                           │
│  ┌────────────────┐                                    │
│  │  database.py   │                                    │
│  │                │                                    │
│  │  - add_user()  │                                    │
│  │  - get_user()  │                                    │
│  │  - update_user()│                                   │
│  │  - ...         │                                    │
│  └───────┬────────┘                                    │
│          │                                              │
│          ▼                                              │
│  ┌────────────────┐                                    │
│  │ studentbuddy.db│  ◄─── SQLite3                     │
│  │                │                                    │
│  │ [users table]  │                                    │
│  └────────────────┘                                    │
│                                                          │
│  Утилиты:                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ migrate_to_  │  │  db_admin.py │  │test_database│ │
│  │   db.py      │  │              │  │    .py      │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Итого

- **1 таблица:** `users`
- **9 полей:** от `user_id` до `updated_at`
- **Простая структура:** легко расширять
- **Надежность:** транзакции и откаты
- **Производительность:** до 10,000+ пользователей
