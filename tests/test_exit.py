import pytest

from src.modules.exit import calculate_exit


def test_exit_equity_positive():
    res = calculate_exit(
        final_year_ebitda=50.0,
        exit_multiple=8.0,
        debt=200.0,
        initial_equity=100.0,
        years=5,
    )
    assert res["Equity Value"] == pytest.approx(200.0)
    assert res["IRR"] is not None and 0 < res["IRR"] < 0.25


def test_exit_invalid_input_raises():
    with pytest.raises(ValueError):
        calculate_exit(50.0, 10.0, 100.0, 0.0, 5)

    with pytest.raises(ValueError):
        calculate_exit(50.0, -2.0, 100.0, 100.0, 5)
