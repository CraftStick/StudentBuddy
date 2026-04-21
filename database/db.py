# -*- coding: utf-8 -*-
"""Модуль для работы с базой данных SQLite3."""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Optional[Dict[str, Any]]:
    """Преобразует sqlite3.Row в словарь с именами колонок (для совместимости)."""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


# Константы для валидации Telegram user_id
MIN_USER_ID = 1
MAX_USER_ID = 9999999999999  # Максимальный user_id в Telegram


def validate_user_id(user_id: int) -> bool:
    """
    Проверяет корректность user_id Telegram.

    Args:
        user_id: ID пользователя для проверки

    Returns:
        True если user_id валиден

    Raises:
        ValueError: Если user_id некорректен
    """
    if not isinstance(user_id, int):
        raise ValueError(f"user_id должен быть целым числом, получено: {type(user_id)}")

    if user_id < MIN_USER_ID or user_id > MAX_USER_ID:
        raise ValueError(f"user_id вне допустимого диапазона ({MIN_USER_ID}-{MAX_USER_ID}): {user_id}")

    return True


class Database:
    """Класс для работы с базой данных пользователей бота."""

    def __init__(self, db_path: str = "studentbuddy.db"):
        """
        Инициализация базы данных.

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для работы с соединением БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Для доступа к полям по имени
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Ошибка при работе с БД: %s", e)
            raise
        finally:
            conn.close()

    def init_db(self):
        """Создание таблиц базы данных."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    name TEXT,
                    building TEXT,
                    student_group TEXT,
                    language TEXT DEFAULT 'ru',
                    notifications_enabled INTEGER DEFAULT 1,
                    reminder_offset_min INTEGER DEFAULT 10,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Добавляем колонку language если её нет (для существующих БД)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
                logger.info("Добавлена колонка language в таблицу users")
            except sqlite3.OperationalError:
                pass

            # Добавляем колонку reminder_offset_min (интервал напоминаний) если её нет
            try:
                cursor.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN reminder_offset_min INTEGER DEFAULT 10"
                )
                logger.info(
                    "Добавлена колонка reminder_offset_min в таблицу users "
                    "(интервал напоминаний, мин)"
                )
            except sqlite3.OperationalError:
                pass

            # Создаём индексы для оптимизации часто используемых запросов
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_notifications_users
                    ON users(notifications_enabled, building, student_group)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_student_group
                    ON users(student_group)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_building
                    ON users(building)
                """)
                logger.info("Индексы базы данных проверены/созданы")
            except sqlite3.OperationalError as e:
                logger.warning("Не удалось создать индексы: %s", e)

            logger.info("База данных инициализирована")

    def add_user(self, user_id: int, username: Optional[str] = None,
                 first_name: Optional[str] = None, name: Optional[str] = None) -> bool:
        """Добавление нового пользователя в базу данных."""
        validate_user_id(user_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, name,
                                     notifications_enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (user_id, username, first_name, name, now, now))
                logger.info("Добавлен новый пользователь: %s", user_id)
                logger.debug("Детали пользователя: username=%s, name=%s", username, name)
                return True
        except sqlite3.IntegrityError:
            logger.debug("Пользователь %s уже существует", user_id)
            return False

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение данных пользователя."""
        validate_user_id(user_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                logger.debug("Пользователь %s найден в БД", user_id)
                return _row_to_dict(row)
            logger.debug("Пользователь %s не найден в БД", user_id)
            return None

    def update_user(self, user_id: int, **kwargs) -> bool:
        """Обновление данных пользователя."""
        validate_user_id(user_id)
        allowed_fields = {
            'building',
            'student_group',
            'notifications_enabled',
            'name',
            'username',
            'first_name',
            'language',
            'reminder_offset_min',
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            logger.warning("Нет полей для обновления")
            return False
        updates['updated_at'] = datetime.now().isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
                query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
                cursor.execute(query, list(updates.values()) + [user_id])
                if cursor.rowcount > 0:
                    logger.info("Обновлены данные пользователя %s", user_id)
                    logger.debug("Изменённые поля: %s", list(updates.keys()))
                    return True
                logger.warning("Пользователь %s не найден для обновления", user_id)
                return False
        except Exception as e:
            logger.error("Ошибка при обновлении пользователя %s: %s", user_id, e)
            return False

    def delete_user(self, user_id: int) -> bool:
        """Удаление пользователя из базы данных."""
        validate_user_id(user_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                if cursor.rowcount > 0:
                    logger.info("Удален пользователь %s", user_id)
                    return True
                logger.debug("Пользователь %s не найден для удаления", user_id)
                return False
        except Exception as e:
            logger.error("Ошибка при удалении пользователя %s: %s", user_id, e)
            return False

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получение всех пользователей."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            logger.debug("Получено %s пользователей из БД", len(rows))
            return [_row_to_dict(row) for row in rows]

    def get_users_with_notifications(self) -> List[Dict[str, Any]]:
        """Получение пользователей с включенными уведомлениями."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    user_id,
                    student_group,
                    building,
                    language,
                    reminder_offset_min
                FROM users
                WHERE notifications_enabled = 1
                  AND building IS NOT NULL
                  AND student_group IS NOT NULL
            """)
            rows = cursor.fetchall()
            logger.debug("Получено %s пользователей с включенными уведомлениями", len(rows))
            return [_row_to_dict(row) for row in rows]

    def set_notifications(self, user_id: int, enabled: bool) -> bool:
        """Включение/отключение уведомлений для пользователя."""
        validate_user_id(user_id)
        return self.update_user(user_id, notifications_enabled=1 if enabled else 0)

    def user_exists(self, user_id: int) -> bool:
        """Проверка существования пользователя в базе данных."""
        validate_user_id(user_id)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
