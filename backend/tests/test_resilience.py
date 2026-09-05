"""Устойчивость HTTP-клиента: throttle, retry, предохранитель"""

from __future__ import annotations

import time

import pytest

from backend.app.exceptions import CircuitOpenError
from backend.app.http_client import CircuitBreaker, RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_enforces_min_interval() -> None:
    """N acquire при min_interval должны занимать не меньше (N-1)*interval"""
    interval = 0.1
    limiter = RateLimiter(min_interval=interval)

    start = time.monotonic()
    await limiter.acquire()  # первый — мгновенно
    await limiter.acquire()  # ждёт interval
    await limiter.acquire()  # ещё interval
    elapsed = time.monotonic() - start

    assert elapsed >= interval * 2 - 0.01


@pytest.mark.asyncio
async def test_rate_limiter_noop_when_interval_zero() -> None:
    """Без интервала троттлинг не мешает (дефолт совместим с прошлым поведением)"""
    limiter = RateLimiter(min_interval=0.0)
    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    assert time.monotonic() - start < 0.1


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures() -> None:
    """Серия подряд упавших 5xx размыкает цепь → fail fast с CircuitOpenError"""
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)

    await breaker.before_request()
    for _ in range(3):
        await breaker.record_failure()

    with pytest.raises(CircuitOpenError):
        await breaker.before_request()


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_after_cooldown() -> None:
    """После cooldown разворачивается пробный запрос; успех замыкает цепь"""
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=1.0)

    await breaker.record_failure()
    await breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        await breaker.before_request()

    breaker._opened_at = time.monotonic() - 2.0  # noqa: SLF001
    await breaker.before_request()
    await breaker.record_success()

    await breaker.before_request()


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_reopens() -> None:
    """Неудачный пробный запрос (half-open) снова размыкает цепь"""
    breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=1.0)

    await breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        await breaker.before_request()

    breaker._opened_at = time.monotonic() - 2.0  # noqa: SLF001
    await breaker.before_request()  # probe разрешён (half-open)
    await breaker.record_failure()  # probe failed

    with pytest.raises(CircuitOpenError):
        await breaker.before_request()
