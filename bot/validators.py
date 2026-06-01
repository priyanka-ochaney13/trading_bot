"""
Input validation for trading bot order parameters.

All validators raise ``ValidationError`` on bad input and return the
(possibly normalised) value on success.  ``validate_order_params`` is the
single entry-point used by orders.py.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger("trading_bot.validators")

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

VALID_SIDES = {"BUY", "SELL"}

# User-facing order types; STOP_LIMIT maps to Binance's "STOP" internally.
SUPPORTED_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}


# ------------------------------------------------------------------
# Exception
# ------------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when a user-supplied value fails validation."""


# ------------------------------------------------------------------
# Individual field validators
# ------------------------------------------------------------------

def validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValidationError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValidationError(
            f"Symbol must be alphanumeric (e.g. BTCUSDT), got: '{symbol}'."
        )
    return symbol


def validate_side(side: str) -> str:
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Side must be BUY or SELL, got: '{side}'."
        )
    return side


def validate_order_type(order_type: str) -> str:
    order_type = order_type.strip().upper()
    if order_type not in SUPPORTED_ORDER_TYPES:
        raise ValidationError(
            f"Order type must be one of {sorted(SUPPORTED_ORDER_TYPES)}, got: '{order_type}'."
        )
    return order_type


def validate_quantity(quantity: float) -> float:
    if quantity <= 0:
        raise ValidationError(
            f"Quantity must be a positive number, got: {quantity}."
        )
    return quantity


def validate_price(
    price: Optional[float],
    *,
    required: bool = False,
    field_name: str = "price",
) -> Optional[float]:
    if required and price is None:
        raise ValidationError(f"'{field_name}' is required for this order type.")
    if price is not None and price <= 0:
        raise ValidationError(
            f"'{field_name}' must be a positive number, got: {price}."
        )
    return price


# ------------------------------------------------------------------
# Composite validator (single public entry-point)
# ------------------------------------------------------------------

def validate_order_params(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
) -> Tuple[str, str, str, float, Optional[float], Optional[float]]:
    """
    Validate all order parameters together, enforcing per-type rules.

    Returns:
        Tuple of (symbol, side, order_type, quantity, price, stop_price)
        with values normalised (uppercased, stripped, etc.).

    Raises:
        ValidationError: if any parameter is invalid or missing.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)

    if order_type == "LIMIT":
        price = validate_price(price, required=True, field_name="price")
    elif order_type == "STOP_LIMIT":
        price = validate_price(price, required=True, field_name="price")
        stop_price = validate_price(stop_price, required=True, field_name="stop_price")
    else:
        # MARKET — price and stop_price are not used
        price = None
        stop_price = None

    logger.debug(
        "Validated: symbol=%s side=%s type=%s qty=%s price=%s stop_price=%s",
        symbol, side, order_type, quantity, price, stop_price,
    )
    return symbol, side, order_type, quantity, price, stop_price
