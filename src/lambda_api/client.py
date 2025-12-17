from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .errors import LambdaCloudError


@dataclass(slots=True)
class _RateLimiter:
    min_interval_seconds: float = 1.0
    launch_min_interval_seconds: float = 12.0

    _last_request_at: float = 0.0
    _last_launch_at: float = 0.0

    def wait(self, path: str) -> None:
        now = time.monotonic()
        last = self._last_request_at
        delay = self.min_interval_seconds - (now - last)
        if delay > 0:
            time.sleep(delay)

        now2 = time.monotonic()
        self._last_request_at = now2

        if path.rstrip("/") == "/instance-operations/launch":
            delay2 = self.launch_min_interval_seconds - (now2 - self._last_launch_at)
            if delay2 > 0:
                time.sleep(delay2)
            self._last_launch_at = time.monotonic()


class LambdaCloudClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://cloud.lambda.ai/api/v1",
        timeout_seconds: float = 30.0,
        rate_limit: bool = True,
    ) -> None:
        self._api_key = api_key or os.environ.get("LAMBDA_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Missing API key. Provide api_key=... or set env var LAMBDA_API_KEY."
            )

        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._rate_limiter = _RateLimiter() if rate_limit else None

        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "accept": "application/json",
                "authorization": f"Bearer {self._api_key}",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LambdaCloudClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> Any:
        norm_path = path if path.startswith("/") else f"/{path}"
        if self._rate_limiter is not None:
            self._rate_limiter.wait(norm_path)

        resp = self._client.request(method, norm_path, params=params, json=json)

        content_type = resp.headers.get("content-type", "")
        response_json: Optional[dict[str, Any]] = None
        if "application/json" in content_type:
            try:
                response_json = resp.json()
            except Exception:
                response_json = None

        if resp.status_code >= 400:
            if response_json and isinstance(response_json.get("error"), dict):
                err = response_json["error"]
                code = str(err.get("code", "unknown"))
                message = str(err.get("message", ""))
                suggestion = err.get("suggestion")
                raise LambdaCloudError(
                    http_status=resp.status_code,
                    code=code,
                    message=message,
                    suggestion=str(suggestion) if suggestion is not None else None,
                    response_json=response_json,
                )
            raise LambdaCloudError(
                http_status=resp.status_code,
                code="unknown",
                message=f"HTTP {resp.status_code}",
                suggestion=None,
                response_json=response_json,
            )

        if response_json is None:
            return None

        # Success envelope is always {"data": <payload>}
        if "data" in response_json:
            return response_json["data"]
        return response_json

    def get(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json: Optional[dict[str, Any]] = None) -> Any:
        return self.request("POST", path, json=json)
