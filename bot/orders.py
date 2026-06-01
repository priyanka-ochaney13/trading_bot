"""
Order placement logic for Binance Futures Testnet.

This module is the middle layer between the CLI (cli.py) and the transport
layer (client.py).  It:
  - Validates input via validators.py
  - Constructs the correct Binance payload for each order type
  - Calls BinanceFuturesClient.place_order()
  - Returns a clean, normalised response dict
"""

import logging
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient
from .validators import validate_order_params

logger = logging.getLogger("trading_bot.orders")


# Binance Futures timeInForce for resting orders
TIME_IN_FORCE = "GTC"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_payload(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    stop_price: Optional[float],
) -> Dict[str, Any]:
    """
    Construct the parameter dict expected by POST /fapi/v1/order.

    User-facing order type "STOP_LIMIT" maps to Binance type "STOP"
    (stop-limit on futures).
    """
    payload: Dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "quantity": f"{quantity:f}",       # avoid scientific notation
    }

    if order_type == "MARKET":
        payload["type"] = "MARKET"

    elif order_type == "LIMIT":
        payload["type"] = "LIMIT"
        payload["timeInForce"] = TIME_IN_FORCE
        payload["price"] = f"{price:f}"

    elif order_type == "STOP_LIMIT":
        # On Binance Futures, type=STOP is a stop-limit order.
        payload["type"] = "STOP"
        payload["timeInForce"] = TIME_IN_FORCE
        payload["price"] = f"{price:f}"
        payload["stopPrice"] = f"{stop_price:f}"

    return payload


def _extract_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pull the fields we care about from the raw Binance response.

    Returns a flat dict suitable for both logging and CLI display.
    """
    return {
        "orderId":     raw.get("orderId"),
        "symbol":      raw.get("symbol"),
        "side":        raw.get("side"),
        "type":        raw.get("origType", raw.get("type")),
        "status":      raw.get("status"),
        "origQty":     raw.get("origQty"),
        "executedQty": raw.get("executedQty"),
        "avgPrice":    raw.get("avgPrice"),
        "price":       raw.get("price"),
        "stopPrice":   raw.get("stopPrice"),
        "timeInForce": raw.get("timeInForce"),
        "updateTime":  raw.get("updateTime"),
    }


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

import time

def _mock_response(symbol, side, order_type, quantity, price, stop_price):
    """Return a realistic fake Binance response for dry runs."""
    binance_type = "STOP" if order_type == "STOP_LIMIT" else order_type
    return {
        "orderId":     99999999,
        "symbol":      symbol,
        "side":        side,
        "type":        binance_type,
        "origType":    binance_type,
        "status":      "FILLED" if order_type == "MARKET" else "NEW",
        "origQty":     f"{quantity:f}",
        "executedQty": f"{quantity:f}" if order_type == "MARKET" else "0",
        "avgPrice":    "67348.20000" if order_type == "MARKET" else "0",
        "price":       f"{price:f}" if price else "0",
        "stopPrice":   f"{stop_price:f}" if stop_price else "0",
        "timeInForce": "GTC",
        "updateTime":  int(time.time() * 1000),
    }


def place_order(
    client,
    symbol,
    side,
    order_type,
    quantity,
    price=None,
    stop_price=None,
    dry_run=False,          # <-- add this
):
    symbol, side, order_type, quantity, price, stop_price = validate_order_params(
        symbol, side, order_type, quantity, price, stop_price
    )

    payload = _build_payload(symbol, side, order_type, quantity, price, stop_price)

    logger.info(
        "Placing order — type=%s side=%s symbol=%s qty=%s price=%s stop_price=%s%s",
        order_type, side, symbol, quantity, price, stop_price,
        " [DRY RUN]" if dry_run else "",
    )

    if dry_run:
        logger.info("Dry run enabled — skipping real API call")
        raw_response = _mock_response(symbol, side, order_type, quantity, price, stop_price)
    else:
        raw_response = client.place_order(**payload)

    result = _extract_response(raw_response)

    logger.info(
        "Order %s — orderId=%s status=%s executedQty=%s avgPrice=%s",
        "simulated" if dry_run else "accepted",
        result["orderId"], result["status"], result["executedQty"], result["avgPrice"],
    )

    return result