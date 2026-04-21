# -*- coding: utf-8 -*-
"""
Health check скрипт для мониторинга состояния бота.

Использование:
    python3 health_check.py

Exit codes:
    0 - Всё работает корректно
    1 - Критическая ошибка (бот не работает)
    2 - Предупреждение (есть проблемы, но бот работает)
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Подгружаем .env из текущей директории (для запуска с сервера и локально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def check_env_variables() -> tuple[bool, str]:
    """Проверка наличия необходимых переменных окружения."""
    required_vars = ["BOT_TOKEN", "SCHEDULE_API_TOKEN"]
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        return False, f"Отсутствуют переменные окружения: {', '.join(missing)}"
    return True, "Переменные окружения: OK"


def check_database() -> tuple[bool, str]:
    """Проверка доступности и целостности базы данных."""
    db_path = os.getenv("DATABASE_PATH", "studentbuddy.db")
    
    if not Path(db_path).exists():
        return False, f"База данных не найдена: {db_path}"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем структуру таблицы users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            conn.close()
            return False, "Таблица users не найдена в БД"
        
        # Проверяем количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        
        # Проверяем индексы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return True, f"База данных: OK ({count} пользователей, {len(indexes)} индексов)"
    except Exception as e:
        return False, f"Ошибка БД: {e}"


def check_locales() -> tuple[bool, str]:
    """Проверка наличия файлов переводов."""
    locales_dir = Path("locales")
    
    if not locales_dir.exists():
        return False, "Директория locales не найдена"
    
    required_langs = ["ru.json", "en.json"]
    missing = []
    
    for lang_file in required_langs:
        if not (locales_dir / lang_file).exists():
            missing.append(lang_file)
    
    if missing:
        return False, f"Отсутствуют файлы переводов: {', '.join(missing)}"
    
    return True, f"Переводы: OK ({len(list(locales_dir.glob('*.json')))} языков)"


def check_persistence_file() -> tuple[bool, str]:
    """Проверка наличия файла persistence (не критично)."""
    persistence_file = os.getenv("PERSISTENCE_FILE", "data/studentbuddy_data.pickle")
    
    if not Path(persistence_file).exists():
        return True, "Persistence файл: отсутствует (создастся при первом запуске)"
    
    # Проверяем возраст файла
    mtime = Path(persistence_file).stat().st_mtime
    age = datetime.now().timestamp() - mtime
    
    if age > 86400:  # Старше 1 дня
        return True, f"Persistence файл: OK (обновлён {int(age/3600)} часов назад)"
    
    return True, "Persistence файл: OK (актуален)"


def check_disk_space() -> tuple[bool, str]:
    """Проверка свободного места на диске."""
    try:
        import shutil
        stat = shutil.disk_usage(".")
        free_gb = stat.free / (1024**3)
        
        if free_gb < 0.1:  # Меньше 100 MB
            return False, f"Критически мало места на диске: {free_gb:.2f} GB"
        elif free_gb < 1:  # Меньше 1 GB
            return True, f"Предупреждение: мало места на диске: {free_gb:.2f} GB"
        
        return True, f"Свободное место: {free_gb:.2f} GB"
    except Exception as e:
        return True, f"Не удалось проверить место: {e}"


def main():
    """Запуск всех проверок."""
    print("=" * 60)
    print("HEALTH CHECK - StudentBuddy Bot")
    print("=" * 60)
    print()
    
    checks = [
        ("Переменные окружения", check_env_variables),
        ("База данных", check_database),
        ("Файлы переводов", check_locales),
        ("Persistence файл", check_persistence_file),
        ("Свободное место", check_disk_space),
    ]
    
    all_ok = True
    warnings = []
    
    for name, check_func in checks:
        try:
            ok, message = check_func()
            status = "✅" if ok else "❌"
            print(f"{status} {name}: {message}")
            
            if not ok:
                all_ok = False
            elif "предупреждение" in message.lower() or "warning" in message.lower():
                warnings.append(message)
        except Exception as e:
            print(f"❌ {name}: Ошибка проверки - {e}")
            all_ok = False
    
    print()
    print("=" * 60)
    
    if all_ok:
        if warnings:
            print("✅ Бот готов к работе (есть предупреждения)")
            print()
            for w in warnings:
                print(f"⚠️  {w}")
            return 2
        else:
            print("✅ Все проверки пройдены! Бот готов к работе.")
            return 0
    else:
        print("❌ Обнаружены критические проблемы!")
        print("   Исправьте ошибки перед запуском бота.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
