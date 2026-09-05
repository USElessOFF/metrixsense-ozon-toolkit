"""HTTP-клиент: throttle, retry, предохранитель"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Self

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.app.exceptions import CircuitOpenError


def _is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


def _is_server_error(exc: BaseException) -> bool:
    """Транзиентные 5xx — имеет смысл повторить"""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Минимальный интервал между запросами одного клиента"""

    def __init__(self, min_interval: float = 0.0):
        self.min_interval = max(0.0, min_interval)
        self._last_request_at = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self.min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._last_request_at + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()


class CircuitBreaker:
    """Предохранитель

    - closed: запросы идут; серия ``failure_threshold`` подряд упавших
      5xx (после исчерпания повторов) размыкает цепь;
    - open: запросы не отправляются — мгновенный ``CircuitOpenError``;
    - half-open: после ``cooldown_seconds`` разрешается один пробный
      запрос; успех замыкает цепь, новая ошибка — снова открывает.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    async def before_request(self) -> None:
        """Разрешить/запретить запрос; при open — выбросить CircuitOpenError"""
        async with self._lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.cooldown_seconds:
                self._opened_at = None
                self._consecutive_failures = 0
                logger.info("Circuit breaker half-open — probe request allowed")
                return
            raise CircuitOpenError(
                "Ozon API временно недоступен (предохранитель разомкнут)"
                f"Повторная попытка через {self.cooldown_seconds - elapsed:.0f} с."
            )

    async def record_success(self) -> None:
        async with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if (
                self._opened_at is None
                and self._consecutive_failures >= self.failure_threshold
            ):
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN after consecutive failures",
                    failures=self._consecutive_failures,
                    cooldown_seconds=self.cooldown_seconds,
                )


class HTTPClient:
    """HTTP-клиент"""

    _default_timeout = 30.0

    def __init__(
        self,
        base_url: str = "",
        timeout: float | None = None,
        min_request_interval: float = 0.0,
        breaker_failure_threshold: int = 5,
        breaker_cooldown_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or self._default_timeout
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = RateLimiter(min_request_interval)
        self._breaker = CircuitBreaker(breaker_failure_threshold, breaker_cooldown_seconds)

    async def _ensure_client(self, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers or {},
            )
        return self._client

    @retry(
        retry=retry_if_exception(_is_rate_limited),
        stop=stop_after_attempt(20),
        wait=wait_exponential(multiplier=1.3, min=10, max=1000),
    )
    @retry(
        retry=retry_if_exception(_is_server_error),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.5, min=2, max=30),
        reraise=True,
    )
    async def request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        base_url: str | None = None,
    ) -> httpx.Response:
        await self._breaker.before_request()
        await self._rate_limiter.acquire()

        url = path
        actual_base = base_url or self.base_url

        if actual_base:
            url = f"{actual_base.rstrip('/')}/{path.lstrip('/')}"

        logger.debug("HTTP request", method=method, url=url)

        client = await self._ensure_client(headers)

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params,
                data=data,
            )
            response.raise_for_status()
            await self._breaker.record_success()
            return response
        except httpx.TimeoutException:
            logger.error("HTTP request timed out", method=method, url=url)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP request failed",
                method=method,
                url=url,
                status_code=e.response.status_code,
                data=data or json or params,
                body=e.response.text[:500],
            )
            # 429 — штатный backoff-ретрай; в предохранитель идут только 5xx
            if e.response.status_code >= 500:
                await self._breaker.record_failure()
            raise
        except httpx.HTTPError as e:
            logger.error("HTTP request error", method=method, url=url, data=data or json or params, error=str(e))
            raise

    async def get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self.request("GET", path, headers=headers, params=params)

    async def post(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
    ) -> httpx.Response:
        return await self.request("POST", path, headers=headers, json=json, data=data)

    async def put(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        return await self.request("PUT", path, headers=headers, json=json)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.close()
