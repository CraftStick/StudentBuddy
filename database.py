# -*- coding: utf-8 -*-
"""Модуль для работы с базой данных SQLite3."""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


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
            logger.error(f"Ошибка при работе с БД: {e}")
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Добавляем колонку language если её нет (для существующих БД)
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
                logger.info("Добавлена колонка language в таблицу users")
            except sqlite3.OperationalError:
                # Колонка уже существует
                pass
            
            logger.info("База данных инициализирована")
    
    def add_user(self, user_id: int, username: Optional[str] = None, 
                 first_name: Optional[str] = None, name: Optional[str] = None) -> bool:
        """
        Добавление нового пользователя в базу данных.
        
        Args:
            user_id: ID пользователя Telegram
            username: Username пользователя
            first_name: Имя пользователя
            name: Отображаемое имя
            
        Returns:
            True если пользователь добавлен, False если уже существует
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, name, 
                                     notifications_enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (user_id, username, first_name, name, now, now))
                
                logger.info(f"Добавлен новый пользователь: {user_id}")
                return True
        except sqlite3.IntegrityError:
            logger.debug(f"Пользователь {user_id} уже существует")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение данных пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Словарь с данными пользователя или None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """
        Обновление данных пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            **kwargs: Поля для обновления (building, student_group, 
                     notifications_enabled, name, username, first_name)
            
        Returns:
            True если обновление успешно
        """
        allowed_fields = {
            'building', 'student_group', 'notifications_enabled',
            'name', 'username', 'first_name', 'language'
        }
        
        # Фильтруем только разрешенные поля
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            logger.warning("Нет полей для обновления")
            return False
        
        # Добавляем updated_at
        updates['updated_at'] = datetime.now().isoformat()
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Формируем запрос
                set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
                query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
                
                cursor.execute(query, list(updates.values()) + [user_id])
                
                if cursor.rowcount > 0:
                    logger.info(f"Обновлены данные пользователя {user_id}: {updates}")
                    return True
                else:
                    logger.warning(f"Пользователь {user_id} не найден")
                    return False
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя {user_id}: {e}")
            return False
    
    def delete_user(self, user_id: int) -> bool:
        """
        Удаление пользователя из базы данных.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если удаление успешно
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"Удален пользователь {user_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {user_id}: {e}")
            return False
    
    def get_all_users(self) -> list[Dict[str, Any]]:
        """
        Получение всех пользователей.
        
        Returns:
            Список словарей с данными пользователей
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_users_with_notifications(self) -> list[Dict[str, Any]]:
        """
        Получение пользователей с включенными уведомлениями.
        
        Returns:
            Список словарей с данными пользователей
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM users 
                WHERE notifications_enabled = 1 
                AND building IS NOT NULL 
                AND student_group IS NOT NULL
            """)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def set_notifications(self, user_id: int, enabled: bool) -> bool:
        """
        Включение/отключение уведомлений для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            enabled: True для включения, False для отключения
            
        Returns:
            True если обновление успешно
        """
        return self.update_user(user_id, notifications_enabled=1 if enabled else 0)
    
    def user_exists(self, user_id: int) -> bool:
        """
        Проверка существования пользователя в базе данных.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            True если пользователь существует
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
