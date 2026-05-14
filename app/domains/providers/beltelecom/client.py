from typing import Any

import httpx

from ..base.exceptions import (
    ProviderPermanentError,
    ProviderTemporaryError,
)


class BeltelecomClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_sec: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password)
        self._timeout = timeout_sec

    async def get_csrf_token(self) -> str:
        response = await self._request("GET", "/session/token", operation="token")
        token = response.text.strip()
        if not token:
            raise ProviderTemporaryError("Beltelecom returned empty CSRF token")
        return token

    async def submit_sms(
        self, payload: dict[str, Any], csrf_token: str
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/webform_rest/submit",
            operation="submit",
            params={"_format": "json"},
            headers={"X-CSRF-Token": csrf_token},
            json=payload,
        )
        return response.json()

    async def get_sms_status(self, sid: str) -> dict[str, Any]:
        response = await self._request(
            "GET",
            "/api/sms/status",
            operation="status",
            params={"sid": sid},
        )
        return response.json()

    async def _request(
        self, method: str, path: str, *, operation: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                auth=self._auth,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method=method, url=path, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise ProviderTemporaryError(f"Beltelecom transport error: {exc}") from exc

        if response.status_code >= 500:
            raise ProviderTemporaryError(
                f"Beltelecom 5xx {operation} error: {response.text}"
            )
        if response.status_code >= 400:
            raise ProviderPermanentError(
                f"Beltelecom 4xx {operation} error: {response.text}"
            )
        return response
