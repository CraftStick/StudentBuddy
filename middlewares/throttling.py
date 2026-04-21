# -*- coding: utf-8 -*-
"""Rate limiter для контроля частоты запросов (in-memory)."""

import time
import logging
from typing import Dict
from collections import deque

logger = logging.getLogger(__name__)


class SimpleRateLimiter:
    """Простой rate limiter с использованием sliding window."""

    _MAX_KEYS = 10000  # максимум ключей в памяти; при превышении удаляем старые

    def __init__(self, max_requests: int = 30, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, deque] = {}

    def is_allowed(self, key: str) -> bool:
        current_time = time.time()
        if len(self.requests) >= self._MAX_KEYS:
            self._cleanup_old_keys(current_time)
        if key not in self.requests:
            self.requests[key] = deque()
        request_times = self.requests[key]
        while request_times and current_time - request_times[0] > self.time_window:
            request_times.popleft()
        if len(request_times) >= self.max_requests:
            logger.warning(
                "Rate limit превышен для %s: %s/%s запросов за %sс",
                key, len(request_times), self.max_requests, self.time_window,
            )
            return False
        request_times.append(current_time)
        return True

    def _cleanup_old_keys(self, current_time: float) -> None:
        to_remove = []
        for k, request_times in self.requests.items():
            while request_times and current_time - request_times[0] > self.time_window:
                request_times.popleft()
            if not request_times:
                to_remove.append(k)
        for k in to_remove[:1000]:
            del self.requests[k]
        if to_remove:
            logger.debug("Rate limiter: удалено %s устаревших ключей", len(to_remove[:1000]))

    def get_wait_time(self, key: str) -> float:
        if key not in self.requests or not self.requests[key]:
            return 0.0
        request_times = self.requests[key]
        if len(request_times) < self.max_requests:
            return 0.0
        oldest_request = request_times[0]
        current_time = time.time()
        wait_time = self.time_window - (current_time - oldest_request)
        return max(0.0, wait_time)

    def reset(self, key: str) -> None:
        if key in self.requests:
            del self.requests[key]
            logger.debug("Rate limiter сброшен для %s", key)


api_rate_limiter = SimpleRateLimiter(max_requests=30, time_window=60)
rate_limiter = api_rate_limiter
