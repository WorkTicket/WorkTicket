from app.ai.schemas import AIOutputSchema
from app.ai.validator import ValidationFailureType, validate_ai_output


def test_validates_valid_output():
    output = AIOutputSchema(
        problem_type="leak",
        summary="Water leak under sink",
        recommended_fix="Replace pipe",
        materials=["pipe", "wrench"],
        estimated_hours=2.0,
        labor_cost_estimate=300.0,
        confidence=0.85,
    )
    result = validate_ai_output(output)
    assert result.valid is True
    assert result.output is not None


def test_rejects_fallback_output():
    output = AIOutputSchema(is_fallback=True)
    result = validate_ai_output(output, reject_on_invalid=True)
    assert result.valid is False
    assert result.failure_type == ValidationFailureType.RECOVERABLE


def test_rejects_low_confidence():
    output = AIOutputSchema(
        summary="test",
        estimated_hours=1.0,
        labor_cost_estimate=100.0,
        confidence=0.1,
    )
    result = validate_ai_output(output, reject_on_invalid=True)
    assert result.valid is False
    assert result.failure_type == ValidationFailureType.RECOVERABLE


def test_rejects_zero_hours():
    output = AIOutputSchema(
        summary="test",
        estimated_hours=0,
        labor_cost_estimate=0,
        confidence=0.9,
    )
    result = validate_ai_output(output, reject_on_invalid=True)
    assert result.valid is False
    assert result.failure_type == ValidationFailureType.NON_RECOVERABLE


def test_schema_rejects_excessive_hours():
    import pytest as _pytest

    with _pytest.raises(ValueError, match="estimated_hours must be between"):
        AIOutputSchema(
            summary="test",
            estimated_hours=500.0,
            labor_cost_estimate=100.0,
            confidence=0.9,
        )


def test_schema_rejects_empty_summary():
    import pytest as _pytest

    with _pytest.raises(ValueError, match="summary cannot be empty"):
        AIOutputSchema(
            summary="",
            estimated_hours=1.0,
            labor_cost_estimate=100.0,
            confidence=0.9,
        )


def test_accepts_degraded_low_confidence_when_not_rejecting():
    output = AIOutputSchema(
        summary="test",
        estimated_hours=1.0,
        labor_cost_estimate=100.0,
        confidence=0.1,
    )
    result = validate_ai_output(output, reject_on_invalid=False)
    assert result.valid is True
    assert "degraded" in str(result.reason).lower() or result.reason
