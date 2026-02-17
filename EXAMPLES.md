# Примеры использования базы данных

## Базовые операции

### Инициализация

```python
from database import Database

# Использовать файл по умолчанию (studentbuddy.db)
db = Database()

# Или указать свой файл
db = Database("my_custom.db")
```

### Добавление пользователя

```python
# При первом обращении пользователя
user = update.effective_user

# Проверяем, существует ли пользователь
if not db.user_exists(user.id):
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        name=user.first_name or user.username
    )
```

### Обновление данных

```python
# Сохранение корпуса
db.update_user(user_id, building="Судостроительная")

# Сохранение группы
db.update_user(user_id, student_group="1ИП-3-25")

# Обновление нескольких полей сразу
db.update_user(
    user_id,
    building="Судостроительная",
    student_group="1ИП-3-25"
)
```

### Получение данных

```python
# Получить пользователя
user = db.get_user(user_id)
if user:
    print(f"Группа: {user['student_group']}")
    print(f"Корпус: {user['building']}")
    print(f"Уведомления: {user['notifications_enabled']}")
```

## Сценарии использования

### 1. Регистрация нового пользователя (команда /start)

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Добавляем или обновляем пользователя
    if not db.user_exists(user.id):
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            name=user.first_name or user.username or "друг"
        )
    else:
        # Обновляем имя на случай изменения
        db.update_user(
            user_id=user.id,
            name=user.first_name or user.username
        )
    
    # Продолжаем диалог выбора корпуса...
```

### 2. Сохранение выбранной группы

```python
async def receive_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Проверка формата группы...
    # Проверка существования группы в API...
    
    # Сохраняем в БД
    db.update_user(user_id, student_group=group)
    
    # И в context для быстрого доступа
    context.user_data["group"] = group
```

### 3. Изменение корпуса/группы (пользователь ошибся)

```python
async def change_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь нажал 'Изменить данные'"""
    user_id = update.effective_user.id
    
    # Начинаем заново - сначала корпус
    await show_buildings_selection(update)
    
    # При выборе нового корпуса
    new_building = selected_building
    db.update_user(user_id, building=new_building)
    
    # При вводе новой группы
    new_group = entered_group
    db.update_user(user_id, student_group=new_group)
    
    # Данные обновлены! Старые данные перезаписаны.
```

### 4. Загрузка данных при запросе расписания

```python
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Пытаемся взять из context (быстро)
    group = context.user_data.get("group")
    building = context.user_data.get("building")
    
    # Если нет в context - загружаем из БД
    if not group:
        user_db = db.get_user(user_id)
        if user_db and user_db.get("student_group"):
            group = user_db["student_group"]
            building = user_db.get("building")
            # Кэшируем в context
            context.user_data["group"] = group
            context.user_data["building"] = building
        else:
            await update.message.reply_text(
                "Сначала укажи корпус и группу: нажми /start."
            )
            return
    
    # Получаем расписание для группы...
```

### 5. Управление уведомлениями

```python
async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Получаем текущее состояние из БД
    user = db.get_user(user_id)
    current_state = user.get("notifications_enabled", 1) if user else True
    
    # Переключаем
    new_state = not current_state
    db.set_notifications(user_id, new_state)
    
    # Обновляем context
    context.user_data["notifications_enabled"] = new_state
    
    # Уведомляем пользователя
    if new_state:
        await query.message.reply_text(
            "🔔 Уведомления включены.\n"
            "Будешь получать напоминания за 10 минут до урока."
        )
    else:
        await query.message.reply_text(
            "🔕 Уведомления выключены.\n"
            "Напоминания приходить не будут."
        )
```

### 6. Рассылка уведомлений

```python
async def send_lesson_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Отправка уведомлений за 10 минут до урока"""
    
    # Получаем всех пользователей с включенными уведомлениями
    users = db.get_users_with_notifications()
    
    for user in users:
        user_id = user["user_id"]
        group = user["student_group"]
        building = user.get("building")
        
        # Получаем расписание для группы
        timetable = await get_timetable(group, building)
        
        # Проверяем, есть ли урок через 10 минут
        next_lesson = find_lesson_in_10_minutes(timetable)
        
        if next_lesson:
            # Отправляем напоминание
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏰ Через 10 минут начинается урок:\n"
                     f"📚 {next_lesson['subject']}\n"
                     f"🚪 Каб. {next_lesson['room']}"
            )
```

### 7. Получение статистики

```python
def show_admin_stats():
    """Статистика для администратора"""
    
    # Все пользователи
    all_users = db.get_all_users()
    print(f"Всего пользователей: {len(all_users)}")
    
    # Пользователи с уведомлениями
    users_with_notif = db.get_users_with_notifications()
    print(f"С уведомлениями: {len(users_with_notif)}")
    
    # Статистика по группам
    groups = {}
    for user in all_users:
        group = user.get("student_group")
        if group:
            groups[group] = groups.get(group, 0) + 1
    
    print(f"Активных групп: {len(groups)}")
    
    # Топ-5 групп
    top_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nТоп-5 групп:")
    for group, count in top_groups:
        print(f"  {group}: {count} студентов")
```

## Продвинутые примеры

### Массовое обновление

```python
# Изменить корпус для всех пользователей группы
def migrate_group_to_building(group_name, new_building):
    all_users = db.get_all_users()
    
    updated = 0
    for user in all_users:
        if user.get("student_group") == group_name:
            db.update_user(user["user_id"], building=new_building)
            updated += 1
    
    print(f"Обновлено пользователей: {updated}")
```

### Очистка неактивных пользователей

```python
from datetime import datetime, timedelta

def cleanup_inactive_users(days=30):
    """Удалить пользователей без группы старше N дней"""
    
    all_users = db.get_all_users()
    cutoff_date = datetime.now() - timedelta(days=days)
    
    removed = 0
    for user in all_users:
        # Пользователь без группы
        if not user.get("student_group"):
            created = datetime.fromisoformat(user["created_at"])
            if created < cutoff_date:
                db.delete_user(user["user_id"])
                removed += 1
    
    print(f"Удалено неактивных пользователей: {removed}")
```

### Экспорт в CSV

```python
import csv

def export_to_csv(filename="users.csv"):
    """Экспорт всех пользователей в CSV"""
    
    users = db.get_all_users()
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'user_id', 'name', 'building', 'student_group',
            'notifications_enabled', 'created_at'
        ])
        writer.writeheader()
        writer.writerows(users)
    
    print(f"Экспортировано пользователей: {len(users)}")
```

### Поиск по группе

```python
def find_users_by_group(group_name):
    """Найти всех пользователей из определенной группы"""
    
    all_users = db.get_all_users()
    return [
        user for user in all_users 
        if user.get("student_group") == group_name
    ]

# Использование
users_from_1ip325 = find_users_by_group("1ИП-3-25")
print(f"Пользователей в группе: {len(users_from_1ip325)}")
```

## Обработка ошибок

### Безопасное обновление

```python
try:
    success = db.update_user(user_id, student_group=new_group)
    if success:
        await update.message.reply_text("✅ Группа обновлена!")
    else:
        await update.message.reply_text(
            "❌ Не удалось обновить группу. Попробуй /start"
        )
except Exception as e:
    logger.error(f"Ошибка при обновлении пользователя: {e}")
    await update.message.reply_text(
        "⚠️ Произошла ошибка. Попробуй позже."
    )
```

### Проверка существования перед операцией

```python
def safe_get_user(user_id):
    """Безопасное получение пользователя"""
    if not db.user_exists(user_id):
        return None
    return db.get_user(user_id)

# Использование
user = safe_get_user(user_id)
if user:
    group = user["student_group"]
else:
    # Пользователь не найден, попросить пройти /start
    pass
```

## Интеграция с context.user_data

### Стратегия кэширования

```python
def get_user_group(user_id, context):
    """Получить группу пользователя с кэшированием"""
    
    # 1. Сначала проверяем context (быстро)
    group = context.user_data.get("group")
    if group:
        return group
    
    # 2. Загружаем из БД (медленнее)
    user = db.get_user(user_id)
    if user and user.get("student_group"):
        group = user["student_group"]
        # Кэшируем в context
        context.user_data["group"] = group
        context.user_data["building"] = user.get("building")
        return group
    
    # 3. Пользователь не настроен
    return None
```

### Синхронизация при изменении

```python
def update_user_group(user_id, context, new_group):
    """Обновить группу везде - в БД и в context"""
    
    # Обновляем в БД (постоянное хранение)
    db.update_user(user_id, student_group=new_group)
    
    # Обновляем в context (быстрый доступ)
    context.user_data["group"] = new_group
    
    logger.info(f"Группа пользователя {user_id} обновлена на {new_group}")
```

## Резервное копирование и восстановление

### Автоматический бэкап при запуске

```python
import shutil
from datetime import datetime

def backup_on_start():
    """Создать бэкап при запуске бота"""
    db_file = "studentbuddy.db"
    if os.path.exists(db_file):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/studentbuddy_backup_{timestamp}.db"
        os.makedirs("backups", exist_ok=True)
        shutil.copy2(db_file, backup_file)
        logger.info(f"Создан бэкап: {backup_file}")

# В bot.py при запуске
if __name__ == "__main__":
    backup_on_start()
    main()
```

### Восстановление из бэкапа

```bash
# Список бэкапов
ls -lh backups/

# Восстановление (остановите бота!)
cp backups/studentbuddy_backup_20260209_123456.db studentbuddy.db

# Запустите бота снова
python3 bot.py
```
