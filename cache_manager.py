# -*- coding: utf-8 -*-
"""Менеджер кэша для хранения ETag и данных API."""

import time
import logging
from typing import Dict, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """Менеджер кэша с поддержкой ETag и TTL."""
    
    def __init__(self, default_ttl: int = 300):
        """
        Инициализация менеджера кэша.
        
        Args:
            default_ttl: Время жизни кэша в секундах (по умолчанию 5 минут)
        """
        self.default_ttl = default_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get_etag(self, key: str) -> Optional[str]:
        """
        Получить ETag для ключа из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            ETag или None если кэш устарел/отсутствует
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Проверяем, не устарел ли кэш
        if time.time() > entry['expires_at']:
            logger.debug(f"Кэш устарел для {key}")
            del self.cache[key]
            return None
        
        return entry.get('etag')
    
    def get_data(self, key: str) -> Optional[Any]:
        """
        Получить данные из кэша.
        
        Args:
            key: Ключ кэша
            
        Returns:
            Закэшированные данные или None
        """
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        
        # Проверяем, не устарел ли кэш
        if time.time() > entry['expires_at']:
            logger.debug(f"Кэш устарел для {key}")
            del self.cache[key]
            return None
        
        logger.debug(f"Кэш hit для {key}")
        return entry.get('data')
    
    def set(self, key: str, data: Any, etag: Optional[str] = None, ttl: Optional[int] = None):
        """
        Сохранить данные и ETag в кэш.
        
        Args:
            key: Ключ кэша
            data: Данные для кэширования
            etag: ETag для HTTP кэширования
            ttl: Время жизни в секундах (опционально)
        """
        if ttl is None:
            ttl = self.default_ttl
        
        self.cache[key] = {
            'data': data,
            'etag': etag,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }
        
        logger.debug(f"Кэш сохранён для {key} (TTL: {ttl}s, ETag: {etag})")
    
    def invalidate(self, key: str):
        """
        Удалить запись из кэша.
        
        Args:
            key: Ключ кэша
        """
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Кэш инвалидирован для {key}")
    
    def clear(self):
        """Очистить весь кэш."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Кэш полностью очищен ({count} записей)")
    
    def cleanup_expired(self):
        """Удалить все устаревшие записи из кэша."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Удалено {len(expired_keys)} устаревших записей из кэша")
    
    def get_cache_key(self, *args) -> str:
        """
        Создать ключ кэша из аргументов.
        
        Args:
            *args: Аргументы для создания ключа
            
        Returns:
            Строковый ключ кэша
        """
        return ":".join(str(arg) for arg in args if arg is not None)


# Глобальный менеджер кэша
cache_manager = CacheManager(default_ttl=300)  # 5 минут
