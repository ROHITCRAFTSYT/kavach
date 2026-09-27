"""Per-client rate limiter.

The app is stateless: user content is never stored server-side (the browser holds the result and
sends it back for follow-up questions), so it can run on serverless platforms and scale horizontally.
Limits are per instance; put a shared store (e.g. Redis) behind this interface for global limits.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    """Sliding-window limiter keyed by client id (IP)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            if len(self._hits) > 10_000:  # bound memory under abuse
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - 60}
            return True
