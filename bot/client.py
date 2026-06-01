"""
Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - HTTP transport (httpx)
  - Structured request / response logging
  - Error normalisation into BinanceAPIError / NetworkError
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("trading_bot.client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_RECV_WINDOW = 5000    # ms — generous enough for testnet latency
REQUEST_TIMEOUT = 30.0        # seconds


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx HTTP status."""

    def __init__(self, status_code: int, raw_body: str) -> None:
        self.status_code = status_code
        try:
            data = json.loads(raw_body)
            self.code: Any = data.get("code", status_code)
            self.msg: str = data.get("msg", raw_body)
        except (json.JSONDecodeError, ValueError):
            self.code = status_code
            self.msg = raw_body
        super().__init__(f"Binance API Error [{self.code}]: {self.msg}")


class NetworkError(Exception):
    """Raised on transport-level failures (DNS, timeout, connection refused)."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API.

    Exposes signed and unsigned request helpers; does **not** contain any
    business logic — that lives in orders.py.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self._session = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            headers={"X-MBX-APIKEY": self.api_key},
        )
        logger.debug("BinanceFuturesClient initialised — base_url=%s", self.base_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        """Return HMAC-SHA256 hex signature of the URL-encoded params."""
        qs = urlencode(params)
        return hmac.new(
            self.api_secret.encode("utf-8"),
            qs.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _safe_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of params with the signature redacted for logging."""
        redacted = dict(params)
        if "signature" in redacted:
            redacted["signature"] = "***"
        return redacted

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        params = dict(params) if params else {}

        if signed:
            params["recvWindow"] = DEFAULT_RECV_WINDOW
            params["timestamp"] = self._timestamp()
            params["signature"] = self._sign(params)

        logger.debug(
            "REQUEST %s %s  params=%s",
            method.upper(),
            url,
            self._safe_params(params),
        )

        try:
            response = self._session.request(method, url, params=params)

            # Log the raw response (truncated to avoid flooding the file)
            body_preview = response.text[:800]
            logger.debug(
                "RESPONSE %s  body=%s%s",
                response.status_code,
                body_preview,
                " [truncated]" if len(response.text) > 800 else "",
            )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as exc:
            raw = exc.response.text
            logger.error(
                "HTTP error %s from %s: %s",
                exc.response.status_code,
                url,
                raw[:400],
            )
            raise BinanceAPIError(exc.response.status_code, raw) from exc

        except httpx.TimeoutException as exc:
            logger.error("Request timed out: %s %s", method, url)
            raise NetworkError(f"Request timed out ({REQUEST_TIMEOUT}s): {exc}") from exc

        except httpx.RequestError as exc:
            logger.error("Network error for %s %s: %s", method, url, exc)
            raise NetworkError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def place_order(self, **kwargs: Any) -> Dict[str, Any]:
        """POST /fapi/v1/order — place a new order."""
        return self._request("POST", "/fapi/v1/order", params=kwargs, signed=True)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """GET /fapi/v1/order — query a single order by ID."""
        return self._request(
            "GET",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_account_info(self) -> Dict[str, Any]:
        """GET /fapi/v2/account — return account balances and positions."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def ping(self) -> bool:
        """Return True if the testnet is reachable."""
        try:
            self._request("GET", "/fapi/v1/ping")
            return True
        except (BinanceAPIError, NetworkError):
            return False

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()

    # Support use as a context manager
    def __enter__(self) -> "BinanceFuturesClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
