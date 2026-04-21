# -*- coding: utf-8 -*-
"""
Redis-бэкенд для кэша расписания (опционально).
При REDIS_URL кэш общий для воркеров; без Redis используется память процесса.
"""

import logging
import pickle
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RedisScheduleBackend:
    """
    Кэш расписания в Redis с TTL.
    Значения сериализуются через pickle (результат get_timetable — tuple[dict|None, str|None]).
    """

    def __init__(self, url: str, key_prefix: str = "sb:schedule:"):
        self._url = url
        self._prefix = key_prefix
        self._client: Optional[Any] = None

    def _client_sync(self):
        """Ленивое создание клиента (синхронно, для инициализации)."""
        if self._client is None:
            import redis.asyncio as redis
            self._client = redis.Redis.from_url(self._url, decode_responses=False)
            logger.info("Redis cache backend connected: %s", self._url.split("@")[-1] if "@" in self._url else self._url)
        return self._client

    @property
    def _redis(self):
        return self._client_sync()

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из Redis или None."""
        try:
            raw = await self._redis.get(self._key(key))
            if raw is None:
                return None
            return pickle.loads(raw)
        except Exception as e:
            logger.warning("Redis cache get failed for %s: %s", key, e)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Сохранить значение в Redis с TTL."""
        try:
            await self._redis.set(
                self._key(key),
                pickle.dumps(value),
                ex=ttl_seconds,
            )
        except Exception as e:
            logger.warning("Redis cache set failed for %s: %s", key, e)

    async def delete(self, key: str) -> None:
        """Удалить ключ из Redis."""
        try:
            await self._redis.delete(self._key(key))
        except Exception as e:
            logger.warning("Redis cache delete failed for %s: %s", key, e)

    async def aclose(self) -> None:
        """Закрыть соединение с Redis (вызвать при остановке бота)."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("Redis cache backend closed")
