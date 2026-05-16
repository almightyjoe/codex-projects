from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests

from .models import SteamAPIError


@dataclass(slots=True)
class RequestManager:
    delay: float = 1.0
    retries: int = 3
    backoff: float = 1.7
    timeout: int = 20
    user_agent: str = "SteamOSINTReportBuilder/2.0 public archival utility"
    cancelled: Any = None

    def _check_cancelled(self) -> None:
        if self.cancelled is not None and self.cancelled.is_set():
            raise SteamAPIError("Collection cancelled.")

    def get(self, url: str, label: str, params: dict[str, Any] | None = None) -> requests.Response:
        last_error = ""
        headers = {"User-Agent": self.user_agent}
        for attempt in range(1, self.retries + 1):
            self._check_cancelled()
            try:
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    time.sleep(self.delay * (self.backoff ** (attempt - 1)))
                    continue
                self._raise_for_status(response, label)
                time.sleep(self.delay)
                return response
            except requests.Timeout:
                last_error = f"{label}: timed out."
            except requests.ConnectionError:
                last_error = f"{label}: network error."
            except requests.RequestException as exc:
                last_error = f"{label}: request failed: {exc}"
            if attempt < self.retries:
                time.sleep(self.delay * (self.backoff ** (attempt - 1)))
        raise SteamAPIError(last_error or f"{label}: request failed.")

    def text(self, url: str, label: str) -> str:
        return self.get(url, label).text

    def json(self, url: str, label: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.get(url, label, params=params).json()
        except json.JSONDecodeError:
            raise SteamAPIError(f"{label}: invalid JSON.")

    @staticmethod
    def _raise_for_status(response: requests.Response, label: str) -> None:
        if response.status_code == 403:
            raise SteamAPIError(f"{label}: forbidden, private, denied, or bad API key.")
        if response.status_code == 404:
            raise SteamAPIError(f"{label}: not found.")
        if response.status_code == 429:
            raise SteamAPIError(f"{label}: rate limited.")
        if response.status_code >= 500:
            raise SteamAPIError(f"{label}: Steam server error {response.status_code}.")
        response.raise_for_status()
