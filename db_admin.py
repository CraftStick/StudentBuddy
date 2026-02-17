# -*- coding: utf-8 -*-
"""
Скрипт для управления базой данных StudentBuddy.

Использование:
    python3 db_admin.py stats          - показать статистику
    python3 db_admin.py list           - список всех пользователей
    python3 db_admin.py user <user_id> - информация о пользователе
    python3 db_admin.py backup         - создать резервную копию
"""

import sys
import os
import shutil
from datetime import datetime
from database import Database


def show_stats():
    """Показать статистику по базе данных."""
    db = Database()
    users = db.get_all_users()
    
    total = len(users)
    with_group = sum(1 for u in users if u.get("student_group"))
    with_notifications = sum(1 for u in users if u.get("notifications_enabled") == 1)
    
    print("\n" + "=" * 50)
    print("СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("=" * 50)
    print(f"Всего пользователей:        {total}")
    print(f"С указанной группой:        {with_group}")
    print(f"С включенными уведомлениями: {with_notifications}")
    print("=" * 50)
    
    # Статистика по корпусам
    buildings = {}
    for u in users:
        building = u.get("building", "Не указан")
        if building:
            buildings[building] = buildings.get(building, 0) + 1
    
    if buildings:
        print("\nПользователи по корпусам:")
        for building, count in sorted(buildings.items(), key=lambda x: x[1], reverse=True):
            print(f"  {building}: {count}")
    
    # Статистика по группам
    groups = {}
    for u in users:
        group = u.get("student_group")
        if group:
            groups[group] = groups.get(group, 0) + 1
    
    if groups:
        print(f"\nВсего групп: {len(groups)}")
        print("\nТоп-10 групп:")
        for group, count in sorted(groups.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {group}: {count}")
    
    print()


def list_users():
    """Показать список всех пользователей."""
    db = Database()
    users = db.get_all_users()
    
    print("\n" + "=" * 80)
    print("СПИСОК ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 80)
    print(f"{'User ID':<12} {'Имя':<20} {'Группа':<15} {'Корпус':<25} {'Уведомления':<12}")
    print("-" * 80)
    
    for user in users:
        user_id = str(user.get("user_id", ""))
        name = user.get("name", "")[:18] or "-"
        group = user.get("student_group", "")[:13] or "-"
        building = user.get("building", "")[:23] or "-"
        notif = "Вкл" if user.get("notifications_enabled") == 1 else "Выкл"
        
        print(f"{user_id:<12} {name:<20} {group:<15} {building:<25} {notif:<12}")
    
    print("=" * 80)
    print(f"Всего: {len(users)}\n")


def show_user(user_id: int):
    """Показать подробную информацию о пользователе."""
    db = Database()
    user = db.get_user(user_id)
    
    if not user:
        print(f"\nПользователь с ID {user_id} не найден в базе данных.\n")
        return
    
    print("\n" + "=" * 50)
    print("ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ")
    print("=" * 50)
    print(f"User ID:          {user.get('user_id')}")
    print(f"Username:         {user.get('username') or '-'}")
    print(f"First Name:       {user.get('first_name') or '-'}")
    print(f"Отображаемое имя: {user.get('name') or '-'}")
    print(f"Корпус:           {user.get('building') or '-'}")
    print(f"Группа:           {user.get('student_group') or '-'}")
    print(f"Уведомления:      {'Включены' if user.get('notifications_enabled') == 1 else 'Выключены'}")
    print(f"Создан:           {user.get('created_at')}")
    print(f"Обновлен:         {user.get('updated_at')}")
    print("=" * 50 + "\n")


def backup_database():
    """Создать резервную копию базы данных."""
    db_file = "studentbuddy.db"
    
    if not os.path.exists(db_file):
        print(f"\nФайл базы данных {db_file} не найден.\n")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"studentbuddy_backup_{timestamp}.db"
    
    try:
        shutil.copy2(db_file, backup_file)
        file_size = os.path.getsize(backup_file)
        print(f"\n✅ Резервная копия создана: {backup_file}")
        print(f"   Размер: {file_size} байт\n")
    except Exception as e:
        print(f"\n❌ Ошибка при создании резервной копии: {e}\n")


def show_help():
    """Показать справку по использованию."""
    print("""
Управление базой данных StudentBuddy

Использование:
    python3 db_admin.py <команда> [аргументы]

Команды:
    stats              - Показать статистику по базе данных
    list               - Показать список всех пользователей
    user <user_id>     - Показать информацию о конкретном пользователе
    backup             - Создать резервную копию базы данных
    help               - Показать эту справку

Примеры:
    python3 db_admin.py stats
    python3 db_admin.py list
    python3 db_admin.py user 123456789
    python3 db_admin.py backup
""")


def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "stats":
        show_stats()
    elif command == "list":
        list_users()
    elif command == "user":
        if len(sys.argv) < 3:
            print("\nОшибка: укажите user_id")
            print("Использование: python3 db_admin.py user <user_id>\n")
            return
        try:
            user_id = int(sys.argv[2])
            show_user(user_id)
        except ValueError:
            print("\nОшибка: user_id должен быть числом\n")
    elif command == "backup":
        backup_database()
    elif command == "help":
        show_help()
    else:
        print(f"\nНеизвестная команда: {command}")
        show_help()


if __name__ == "__main__":
    main()
