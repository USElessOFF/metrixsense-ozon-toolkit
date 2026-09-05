"""Клиент Ozon Performance API"""

from __future__ import annotations

import asyncio
import io
import os
import re
import time
from typing import Any

import aiofiles
import httpx
import structlog

from backend.app.exceptions import OzonAPIError
from backend.app.http_client import HTTPClient
from backend.app.pydantic_models.ozon.performance.enums import StatisticsRequestState
from backend.app.pydantic_models.ozon.performance.request import (
    CampaignQueryParams,
    DailyStatsQueryParams,
    StatisticsRequest,
)
from backend.app.pydantic_models.ozon.performance.response import (
    CampaignsList,
    StatisticsReport,
    StatisticsRequestID,
    StatisticsResponse,
)

logger = structlog.get_logger(__name__)


class OzonPerformanceClient:
    """Клиент Performance API (реклама)"""

    BASE_URL = "https://api-performance.ozon.ru"
    TOKEN_PATH = "/api/client/token"
    MIN_REQUEST_INTERVAL_SECONDS = 1.0

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = HTTPClient(timeout=30.0)
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._request_lock = asyncio.Semaphore(1)
        self._last_request_ts: float = 0.0

    async def _ensure_token(self) -> str | None:
        import time as time_module
        now = time_module.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token
        token = await self._fetch_token()
        self._token = token["access_token"]
        self._token_expires_at = now + token.get("expires_in", 3600)
        return self._token

    async def _fetch_token(self) -> dict[str, Any]:
        try:
            resp = await self._http.request(
                "POST",
                self.TOKEN_PATH,
                base_url=self.BASE_URL,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            data = resp.json()
            logger.info("::_fetch_token> Performance token acquired")
            self._last_request_ts = time.monotonic()
            return data
        except Exception as e:
            logger.exception("::_fetch_token> Failed to fetch Performance token", error=str(e))
            raise OzonAPIError("Could not obtain Performance API token") from e


    async def _request(self, method: str, path: str, **kwargs: dict[str, Any]):
        async with self._request_lock:
            now = time.monotonic()
            since_last = now - self._last_request_ts
            if self._last_request_ts and since_last < self.MIN_REQUEST_INTERVAL_SECONDS:
                await asyncio.sleep(self.MIN_REQUEST_INTERVAL_SECONDS - since_last)
            token = await self._ensure_token()
            headers: dict[str, Any] = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                **(kwargs.pop("headers", {})),
            }
            resp = await self._http.request(method, path, base_url=self.BASE_URL, headers=headers, **kwargs)
            self._last_request_ts = time.monotonic()
            return resp

    async def check_connection(self) -> bool:
        try:
            await self._ensure_token()
            return True
        except Exception as e:
            logger.exception("::check_connection> Performance API check failed", error=str(e))
            return False

    async def list_campaigns(self, request: CampaignQueryParams) -> CampaignsList:
        request_params = request.model_dump(exclude_none=True)
        resp = await self._request("GET", "/api/client/campaign", params=request_params)
        resp = resp.json()
        logger.info(f"::list_campaigns <{request_params}>>: {resp}")
        return CampaignsList.model_validate(resp)

    async def get_campaign_daily_stats(self, data: DailyStatsQueryParams) -> StatisticsReport:
        params = data.to_query_params()
        resp = (await self._request("GET", "/api/client/statistics/daily", params=params)).json()
        return StatisticsReport.model_validate(resp)
    
    async def get_campaign_daily_stats_buffer(self, data: DailyStatsQueryParams) -> io.BytesIO:
        params = data.to_query_params()
        resp = await self._request("GET", "/api/client/statistics/daily", params=params)
        return await self._get_bytesio_from_resp(resp)

    async def submit_statistics(self, request: StatisticsRequest) -> StatisticsRequestID:
        payload = request.model_dump(exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/api/client/statistics", json=payload)
        resp_json = resp.json()
        logger.info(f"::submit_statistics <{resp.status_code}>: {resp_json}")
        return StatisticsRequestID.model_validate(resp_json)

    async def wait_report(
        self, report_data: list[StatisticsRequestID], only_wait: bool = False, timeout: int = 3600
    ) -> bool:
        import time as time_module
        time_start = time_module.time()
        while report_data and (time_module.time() - time_start) < timeout:
            for report in list(report_data):
                if not report.uuid:
                    logger.error("::wait_report> unable get UUID for report")
                    raise RuntimeError
                resp = await self.check_statistics_status(report.uuid)
                if resp.state == StatisticsRequestState.OK:
                    if only_wait:
                        logger.info(f"::wait_report> statistics ready: {resp.uuid}")
                        report_data.remove(report)
                        continue
                    if resp.uuid:
                        await self.download_statistics(resp.uuid)
                        report_data.remove(report)
                        logger.info(f"::wait_report> statistics downloaded: {resp.uuid}")
                    else:
                        raise OzonAPIError("::wait_report> Report downloading error, uuid is None")
                elif resp.state == StatisticsRequestState.ERROR:
                    raise OzonAPIError(resp.error or "Report compilation error")
                else:
                    logger.info(f"::wait_report> statistics wait: {resp.uuid}")
                await asyncio.sleep(5)
            await asyncio.sleep(60)
        return True

    async def download_statistics_buffer(self, request_id: str) -> io.BytesIO:
        resp = await self._request("GET", "/api/client/statistics/report", params={"UUID": request_id})
        logger.info(f"::download_statistics_buffer <{request_id}>> : {resp.status_code}")
        return await self._get_bytesio_from_resp(resp)

    async def check_statistics_status(self, request_id: str) -> StatisticsResponse:
        path = f"/api/client/statistics/{request_id}"
        resp = (await self._request("GET", path)).json()
        logger.info(f"::check_statistics_status> Statistics status: {resp}")
        return StatisticsResponse.model_validate(resp)

    async def download_statistics(self, request_id: str, path_to_save: str = "./files") -> str:
        resp = await self._request("GET", "/api/client/statistics/report", params={"UUID": request_id})
        logger.info(f"::download_statistics <{request_id}>> : {resp.status_code}")
        return await self._save_attachment(resp, path_to_save)
    
    async def _get_bytesio_from_resp(self, resp: httpx.Response) -> io.BytesIO:
        buffer = io.BytesIO()
        for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
            buffer.write(chunk)
        buffer.seek(0)
        return buffer
    
    async def _save_attachment(self, response: httpx.Response, directory: str = "./files") -> str:
        if response.status_code != 200:
            logger.info(
                f"::save_attachment> Response status code is {response.status_code}, not saving attachment."
            )
            raise ValueError
        if "content-disposition" in response.headers:
            disposition = response.headers["content-disposition"]
            if disposition.startswith("attachment"):
                match = re.search(r'filename="(.*?)"', disposition)
                if match:
                    filename = os.path.basename(match.group(1))
                    os.makedirs(directory, exist_ok=True)
                    filepath = os.path.join(directory, filename)
                    if os.path.exists(filepath):
                        logger.info(f"::save_attachment> File {filepath} already exists. Overwriting.")
                    try:
                        async with aiofiles.open(filepath, "wb") as f:
                            for chunk in response.iter_bytes():
                                await f.write(chunk)
                        logger.info(f"::save_attachment> File saved to {filepath}")
                        return filepath
                    except Exception:
                        logger.exception("::save_attachment> Error saving file")
                        raise 
                else:
                    logger.info("::save_attachment> No filename found in content-disposition header.")
                    raise ValueError
            else:
                logger.info("::save_attachment> Content-Disposition does not indicate an attachment.")
                raise ValueError
        else:
            logger.info("::save_attachment> No Content-Disposition header found in the response.")
            raise ValueError
    
    async def close(self):
        await self._http.close()
