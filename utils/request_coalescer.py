# -*- coding: utf-8 -*-
"""
Request coalescing: при множестве одновременных запросов с одним ключом
выполняется один вызов fetch_func, остальные ждут тот же результат.
Кэш можно хранить в памяти или в Redis (REDIS_URL).
"""

import asyncio
import time
from typing import Any, Callable, Optional, Protocol, TypeVar

T = TypeVar("T")


class ScheduleCacheBackend(Protocol):
    """Протокол бэкенда кэша: Redis или in-memory."""

    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...


class RequestCoalescer:
    """
    Схлопывание запросов по ключу: один активный запрос на ключ,
    остальные ждут через asyncio.Future. Результат кэшируется с TTL
    (в памяти или в Redis, если передан backend).
    """

    def __init__(self, ttl: int = 600, backend: Optional[ScheduleCacheBackend] = None):
        """
        Args:
            ttl: Время жизни кэша в секундах (по умолчанию 600 = 10 минут).
            backend: Опциональный бэкенд (Redis). Если None — кэш в памяти.
        """
        self._ttl = ttl
        self._backend = backend
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (result, expires_at), только если backend is None
        self._in_flight: dict[str, asyncio.Future] = {}  # key -> Future

    async def get(self, key: str, fetch_func: Callable[[], T]) -> T:
        """
        Получить данные по ключу: из кэша, из выполняющегося запроса или выполнить fetch_func.

        - Если есть свежий кэш (память или Redis) — вернуть сразу.
        - Если запрос по этому ключу уже выполняется — ждать его результат.
        - Иначе выполнить fetch_func() (синхронно в потоке), закэшировать и вернуть результат.

        Args:
            key: Ключ кэша (например "schedule:1ИП-3-25:current:3").
            fetch_func: Синхронная функция без аргументов, возвращающая результат запроса.

        Returns:
            Результат fetch_func() или закэшированное значение.
        """
        # 1. Проверяем кэш (Redis или память)
        if self._backend is not None:
            cached = await self._backend.get(key)
            if cached is not None:
                return cached
        else:
            now = time.time()
            if key in self._cache:
                result, expires_at = self._cache[key]
                if now <= expires_at:
                    return result
                del self._cache[key]

        # 2. Уже выполняется запрос по этому ключу — ждём
        if key in self._in_flight:
            future = self._in_flight[key]
            return await future

        # 3. Запускаем единственный запрос
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._in_flight[key] = future

        try:
            result = await asyncio.to_thread(fetch_func)
            if self._backend is not None:
                await self._backend.set(key, result, self._ttl)
            else:
                self._cache[key] = (result, time.time() + self._ttl)
            if not future.done():
                future.set_result(result)
            return result
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            self._in_flight.pop(key, None)

    async def clear(self, key: str) -> None:
        """
        Удалить запись из кэша по ключу.
        Выполняющийся запрос по этому ключу не отменяется.
        """
        if self._backend is not None:
            await self._backend.delete(key)
        elif key in self._cache:
            del self._cache[key]
