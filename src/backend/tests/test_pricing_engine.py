from app.pricing.engine import (
    _round_currency,
    apply_markup,
    apply_rounding,
    compute_line_item_total,
    compute_subtotal,
    compute_total,
    recompute_estimate,
    recompute_line_item,
    validate_estimate,
    validate_line_item,
)


class TestRoundCurrency:
    def test_rounds_to_two_decimals(self):
        assert _round_currency(10.456) == 10.46
        assert _round_currency(10.454) == 10.45

    def test_handles_half_up(self):
        assert _round_currency(10.455) == 10.46

    def test_handles_integers(self):
        assert _round_currency(10) == 10.0


class TestComputeLineItemTotal:
    def test_basic_multiplication(self):
        assert compute_line_item_total(2, 150) == 300.0

    def test_rounding(self):
        assert compute_line_item_total(1.5, 99.99) == 149.99

    def test_zero_quantity(self):
        assert compute_line_item_total(0, 150) == 0.0

    def test_zero_rate(self):
        assert compute_line_item_total(2, 0) == 0.0


class TestComputeSubtotal:
    def test_sums_line_items(self):
        items = [{"total": 100.0}, {"total": 200.0}, {"total": 50.50}]
        assert compute_subtotal(items) == 350.50

    def test_empty_items(self):
        assert compute_subtotal([]) == 0.0

    def test_single_item(self):
        assert compute_subtotal([{"total": 99.99}]) == 99.99


class TestComputeTotal:
    def test_subtotal_plus_tax(self):
        assert compute_total(300.0, 30.0) == 330.0

    def test_zero_tax(self):
        assert compute_total(100.0, 0.0) == 100.0

    def test_rounding(self):
        assert compute_total(100.123, 10.012) == 110.14


class TestRecomputeLineItem:
    def test_recomputes_total(self):
        result = recompute_line_item({"name": "Labor", "quantity": 2, "rate": 150, "total": 999})
        assert result["total"] == 300.0

    def test_handles_missing_total(self):
        result = recompute_line_item({"name": "Labor", "quantity": 2, "rate": 150})
        assert result["total"] == 300.0

    def test_preserves_extra_fields(self):
        result = recompute_line_item({"name": "Test", "quantity": 3, "rate": 50, "item_type": "labor", "note": "x"})
        assert result["total"] == 150.0
        assert result["item_type"] == "labor"
        assert result["note"] == "x"


class TestRecomputeEstimate:
    def test_recomputes_estimate_totals(self):
        estimate = {
            "line_items": [
                {"name": "Labor", "quantity": 2, "rate": 150, "total": 0},
                {"name": "Materials", "quantity": 1, "rate": 300, "total": 0},
            ],
            "tax": 45.0,
            "subtotal": 0,
            "total": 0,
        }
        result = recompute_estimate(estimate)
        assert result["subtotal"] == 600.0
        assert result["total"] == 645.0
        assert result["line_items"][0]["total"] == 300.0
        assert result["line_items"][1]["total"] == 300.0

    def test_empty_line_items(self):
        result = recompute_estimate({"line_items": [], "tax": 10})
        assert result["subtotal"] == 0.0
        assert result["total"] == 10.0


class TestValidateLineItem:
    def test_valid_item_passes(self):
        errors = validate_line_item(
            {"name": "Labor", "item_type": "labor", "quantity": 2, "rate": 150, "total": 300}, 0
        )
        assert errors == []

    def test_rejects_empty_name(self):
        errors = validate_line_item({"name": "", "item_type": "labor", "quantity": 1, "rate": 100, "total": 100}, 0)
        assert any("name" in e for e in errors)

    def test_rejects_invalid_item_type(self):
        errors = validate_line_item({"name": "X", "item_type": "invalid", "quantity": 1, "rate": 100, "total": 100}, 0)
        assert any("item_type" in e for e in errors)

    def test_rejects_negative_quantity(self):
        errors = validate_line_item({"name": "X", "item_type": "labor", "quantity": -1, "rate": 100, "total": 0}, 0)
        assert any("quantity" in e for e in errors)

    def test_rejects_negative_rate(self):
        errors = validate_line_item({"name": "X", "item_type": "labor", "quantity": 1, "rate": -10, "total": 0}, 0)
        assert any("rate" in e for e in errors)

    def test_rejects_mismatched_total(self):
        errors = validate_line_item({"name": "X", "item_type": "labor", "quantity": 2, "rate": 150, "total": 999}, 0)
        assert any("total" in e for e in errors)

    def test_accepts_rounded_total(self):
        errors = validate_line_item(
            {"name": "X", "item_type": "labor", "quantity": 1.5, "rate": 99.99, "total": 149.99}, 0
        )
        assert errors == []

    def test_missing_quantity(self):
        errors = validate_line_item({"name": "X", "item_type": "labor", "rate": 100, "total": 0}, 0)
        assert any("quantity" in e for e in errors)


class TestValidateEstimate:
    def test_valid_estimate_passes(self):
        estimate = {
            "line_items": [
                {"name": "Labor", "item_type": "labor", "quantity": 2, "rate": 150, "total": 300},
            ],
            "subtotal": 300,
            "tax": 30,
            "total": 330,
        }
        errors = validate_estimate(estimate)
        assert errors == []

    def test_rejects_mismatched_subtotal(self):
        estimate = {
            "line_items": [
                {"name": "Labor", "item_type": "labor", "quantity": 2, "rate": 150, "total": 300},
            ],
            "subtotal": 999,
            "tax": 0,
            "total": 300,
        }
        errors = validate_estimate(estimate)
        assert any("subtotal" in e for e in errors)

    def test_rejects_mismatched_total(self):
        estimate = {
            "line_items": [
                {"name": "Labor", "item_type": "labor", "quantity": 2, "rate": 150, "total": 300},
            ],
            "subtotal": 300,
            "tax": 30,
            "total": 999,
        }
        errors = validate_estimate(estimate)
        assert any("total" in e for e in errors)


class TestApplyMarkup:
    def test_basic_markup(self):
        assert apply_markup(100, 25) == 125.0

    def test_zero_markup(self):
        assert apply_markup(100, 0) == 100.0

    def test_rounding(self):
        assert apply_markup(99.99, 10) == 109.99


class TestApplyRounding:
    def test_nearest_dollar(self):
        assert apply_rounding(10.50, "nearest_dollar") == 11.0

    def test_default_rounding(self):
        assert apply_rounding(10.456, "30_min") == 10.46
