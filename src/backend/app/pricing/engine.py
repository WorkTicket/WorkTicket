import logging
from decimal import ROUND_HALF_UP, Decimal

logger = logging.getLogger(__name__)

LINE_ITEM_TYPES = ["labor", "materials", "fee"]


def _to_decimal(value: float) -> Decimal:
    """Safely convert a float to Decimal without floating-point artifacts."""
    return Decimal(str(value))


def _round_currency(value: float) -> float:
    """Round to 2 decimal places using HALF_UP rounding (canonical for all pricing)."""
    return float(_to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _round_currency_decimal(d: Decimal) -> float:
    """Round a Decimal to 2 decimal places using HALF_UP rounding."""
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_line_item_total(quantity: float, rate: float) -> float:
    """Compute canonical line item total = quantity * rate, rounded.

    Uses Decimal arithmetic to avoid floating-point rounding errors
    (e.g., 1.5 * 99.99 = 149.985 → rounds to 149.99, not 149.98).
    """
    q = _to_decimal(quantity)
    r = _to_decimal(rate)
    return _round_currency_decimal(q * r)


def compute_subtotal(line_items: list[dict]) -> float:
    """Compute canonical subtotal from line item totals."""
    return _round_currency(sum(item.get("total", 0) for item in line_items))


def compute_total(subtotal: float, tax: float) -> float:
    """Compute canonical total = subtotal + tax."""
    return _round_currency(subtotal + tax)


def apply_markup(value: float, markup_percent: float) -> float:
    """Apply percentage markup to a value."""
    return _round_currency(value * (1 + markup_percent / 100))


def apply_rounding(value: float, rule: str) -> float:
    """Apply rounding rule (e.g. '30_min', '15_min', 'nearest_dollar')."""
    if rule == "nearest_dollar":
        return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if rule == "30_min":
        return _round_currency(value)
    if rule == "15_min":
        return _round_currency(value)
    return _round_currency(value)


def recompute_line_item(item: dict) -> dict:
    """Enrich a line item with its canonical total."""
    qty = float(item.get("quantity", 0))
    rate = float(item.get("rate", 0))
    computed = compute_line_item_total(qty, rate)
    return {**item, "total": computed}


def recompute_estimate(estimate: dict) -> dict:
    """Recompute all totals in an estimate from raw line items."""
    items = [recompute_line_item(li) for li in estimate.get("line_items", [])]
    subtotal = compute_subtotal(items)
    tax = _round_currency(float(estimate.get("tax", 0)))
    total = compute_total(subtotal, tax)
    return {
        **estimate,
        "line_items": items,
        "subtotal": subtotal,
        "total": total,
    }


def validate_line_item(item: dict, idx: int = 0) -> list[str]:
    """Validate a single line item. Returns list of error messages."""
    errors: list[str] = []
    name = item.get("name")
    if not name or not str(name).strip():
        errors.append(f"line_items[{idx}].name: must be non-empty")
    item_type = item.get("item_type")
    if item_type not in LINE_ITEM_TYPES:
        errors.append(f"line_items[{idx}].item_type: must be one of {LINE_ITEM_TYPES}, got '{item_type}'")
    quantity = item.get("quantity")
    if quantity is None:
        errors.append(f"line_items[{idx}].quantity: is required")
    else:
        try:
            qty = float(quantity)
            if qty < 0:
                errors.append(f"line_items[{idx}].quantity: must be >= 0, got {qty}")
        except (ValueError, TypeError):
            errors.append(f"line_items[{idx}].quantity: must be a number, got {quantity!r}")
    rate = item.get("rate")
    if rate is None:
        errors.append(f"line_items[{idx}].rate: is required")
    else:
        try:
            r = float(rate)
            if r < 0:
                errors.append(f"line_items[{idx}].rate: must be >= 0, got {r}")
        except (ValueError, TypeError):
            errors.append(f"line_items[{idx}].rate: must be a number, got {rate!r}")
    computed_total = compute_line_item_total(
        float(item.get("quantity", 0)),
        float(item.get("rate", 0)),
    )
    provided_total = item.get("total", 0)
    try:
        if abs(float(provided_total) - computed_total) > 0.02:
            errors.append(
                f"line_items[{idx}].total: {provided_total} does not match computed total {computed_total} "
                f"({item.get('quantity')} * {item.get('rate')})"
            )
    except (ValueError, TypeError):
        errors.append(f"line_items[{idx}].total: must be a number, got {provided_total!r}")
    return errors


def validate_estimate(estimate: dict) -> list[str]:
    """Validate an entire estimate. Returns list of error messages."""
    errors: list[str] = []
    line_items = estimate.get("line_items", [])
    if not isinstance(line_items, list):
        return ["line_items: must be a list"]
    for idx, item in enumerate(line_items):
        errors.extend(validate_line_item(item, idx))
    computed_subtotal = compute_subtotal(line_items)
    provided_subtotal = estimate.get("subtotal")
    if provided_subtotal is not None:
        try:
            if abs(float(provided_subtotal) - computed_subtotal) > 0.02:
                errors.append(f"subtotal: {provided_subtotal} does not match computed subtotal {computed_subtotal}")
        except (ValueError, TypeError):
            errors.append(f"subtotal: must be a number, got {provided_subtotal!r}")
    computed_total = compute_total(computed_subtotal, float(estimate.get("tax", 0)))
    provided_total = estimate.get("total")
    if provided_total is not None:
        try:
            if abs(float(provided_total) - computed_total) > 0.02:
                errors.append(
                    f"total: {provided_total} does not match computed total {computed_total} "
                    f"(subtotal={computed_subtotal} + tax={estimate.get('tax', 0)})"
                )
        except (ValueError, TypeError):
            errors.append(f"total: must be a number, got {provided_total!r}")
    return errors
