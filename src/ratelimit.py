"""Ограничение числа неудачных попыток входа (защита от подбора пароля).

Счётчик хранится в памяти процесса и ведётся отдельно для каждой пары «адрес клиента + логин»:
так злоумышленник блокирует только свои попытки и не может закрыть вход настоящему пользователю
со своего адреса. После перезапуска приложения счётчики обнуляются.
"""
import math
import threading
import time

PRUNE_LIMIT = 10_000   # сколько ключей храним, прежде чем чистить устаревшие


class LoginLimiter:
    def __init__(self, max_attempts, window_seconds, clock=time.monotonic):
        self.max_attempts = max_attempts      # 0 отключает ограничение
        self.window = window_seconds
        self._clock = clock
        self._failures = {}                   # ключ -> список моментов неудачных попыток
        self._lock = threading.Lock()

    def _recent(self, key, now):
        times = [t for t in self._failures.get(key, []) if now - t < self.window]
        if times:
            self._failures[key] = times
        else:
            self._failures.pop(key, None)
        return times

    def retry_after(self, key):
        """Сколько секунд ещё нельзя пробовать войти (0, если можно)."""
        if self.max_attempts <= 0:
            return 0
        with self._lock:
            now = self._clock()
            times = self._recent(key, now)
            if len(times) < self.max_attempts:
                return 0
            return max(1, math.ceil(self.window - (now - times[0])))

    def fail(self, key):
        if self.max_attempts <= 0:
            return
        with self._lock:
            now = self._clock()
            if len(self._failures) >= PRUNE_LIMIT:
                for old_key in list(self._failures):
                    self._recent(old_key, now)
            self._failures.setdefault(key, []).append(now)

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)
