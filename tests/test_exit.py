# tests/test_exit.py
import pytest

from src.modules.exit import calculate_exit


def test_standard_exit_calculation():
    """Terminal, equity, and IRR should compute correctly."""
    out = calculate_exit(
        final_year_ebitda=20.0,
        exit_multiple=5.0,
        debt=30.0,
        initial_equity=50.0,
        years=2,
    )
    # Terminal = 100, equity = 70, IRR = (70/50)^(1/2)-1
    assert out["Terminal Value"] == 100.0
    assert out["Equity Value"] == 70.0
    assert pytest.approx(out["IRR"], rel=1e-6) == (70.0 / 50.0) ** 0.5 - 1


@pytest.mark.parametrize(
    "bad_years,bad_equity,bad_multiple",
    [
        (0, 10.0, 1.0),
        (1, 0.0, 1.0),
        (1, 10.0, -1.0),
    ],
)
def test_invalid_inputs_raise(bad_years, bad_equity, bad_multiple):
    """Years ≤ 0, equity ≤ 0, multiple < 0 should raise ValueError."""
    with pytest.raises(ValueError):
        calculate_exit(
            10.0, bad_multiple, debt=5.0, initial_equity=bad_equity, years=bad_years
        )


def test_negative_equity_capped_irr():
    """If equity value < 0, IRR returns -1.0 per code logic."""
    # EV=EBITDA×mult=100, equity=100-200=-100 → negative => IRR = -1.0
    out = calculate_exit(20.0, 5.0, debt=200.0, initial_equity=100.0, years=2)
    assert out["Equity Value"] == -100.0
    assert out["IRR"] == -1.0
