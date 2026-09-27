from types import SimpleNamespace

import pytest

from kavach import store as store_mod
from kavach.models import Modality, Segment, Source
from kavach.store import RateLimiter


class Clock:
    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def time(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(store_mod, "time", SimpleNamespace(time=c.time))
    return c


def _source() -> Source:
    return Source(modality=Modality.text, segments=[Segment(id="t1", text="hi")])


def test_rate_limiter_allows_n_then_blocks(clock):
    rl = RateLimiter(per_minute=3)
    assert [rl.allow("1.2.3.4") for _ in range(4)] == [True, True, True, False]
    assert rl.allow("5.6.7.8") is True  # other clients unaffected
    clock.now += 61
    assert rl.allow("1.2.3.4") is True
