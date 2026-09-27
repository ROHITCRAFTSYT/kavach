"""Lightweight per-request tracing: which Sarvam APIs ran, how long, and whether they failed."""

from __future__ import annotations

import contextvars
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

log = logging.getLogger("kavach")


@dataclass
class Span:
    name: str
    api: str
    ms: int = 0
    ok: bool = True
    detail: str = ""


@dataclass
class Trace:
    request_id: str
    spans: list[Span] = field(default_factory=list)

    def as_list(self) -> list[dict]:
        return [s.__dict__ for s in self.spans]


_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("kavach_trace", default=None)


def start(request_id: str) -> Trace:
    trace = Trace(request_id)
    _current.set(trace)
    return trace


def current() -> Trace | None:
    return _current.get()


@contextmanager
def span(name: str, api: str):
    s = Span(name=name, api=api)
    t0 = time.perf_counter()
    try:
        yield s
    except Exception as exc:
        s.ok = False
        s.detail = s.detail or type(exc).__name__
        raise
    finally:
        s.ms = int((time.perf_counter() - t0) * 1000)
        trace = _current.get()
        if trace is not None:
            trace.spans.append(s)
        log.info("span %s api=%s ms=%d ok=%s %s", name, api, s.ms, s.ok, s.detail)
