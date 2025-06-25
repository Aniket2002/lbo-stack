# tests/test_cashflow.py
import pytest

from src.modules.cashflow import project_cashflows


@pytest.mark.parametrize(
    "debt, amort_schedule, expected_end_debt",
    [
        (100.0, [0.0, 0.0, 0.0], 100.0),  # no amortization
        (90.0, [30.0, 30.0, 30.0], 0.0),  # full amortization
        (50.0, [25.0, 25.0, 0.0], 0.0),  # partial then zero
    ],
)
def test_debt_amortization(debt, amort_schedule, expected_end_debt):
    """Ending debt should reflect amort schedule, never negative."""
    results = project_cashflows(
        revenue=100.0,
        rev_growth=0.0,
        ebitda_margin=0.2,
        capex_pct=0.05,
        debt=debt,
        interest_rate=0.1,
        tax_rate=0.25,
        years=3,
        debt_amort_schedule=amort_schedule,
    )
    assert results["Year 3"]["Ending Debt"] == pytest.approx(expected_end_debt)


def test_basic_metrics_and_signs():
    """Check that all keys are present and signs make sense."""
    res = project_cashflows(
        revenue=100.0,
        rev_growth=0.1,
        ebitda_margin=0.25,
        capex_pct=0.1,
        debt=50.0,
        interest_rate=0.05,
        tax_rate=0.3,
        years=2,
        debt_amort_schedule=[0.0, 0.0],
    )
    for year in ["Year 1", "Year 2"]:
        row = res[year]
        # Revenue should grow
        assert row["Revenue"] > 100.0
        # EBITDA > 0, CapEx > 0
        assert row["EBITDA"] == pytest.approx(row["Revenue"] * 0.25)
        assert row["CapEx"] == pytest.approx(row["Revenue"] * 0.1)
        # Interest and Levered FCF keys exist
        assert "Interest" in row and "Levered FCF" in row
        # Tax is zero if EBT < 0
        if row["EBT"] < 0:
            assert row["Tax"] == 0.0
        else:
            assert row["Tax"] == pytest.approx(row["EBT"] * 0.3)


def test_invalid_years_or_schedule():
    """Negative or mismatched inputs should not crash silently."""
    with pytest.raises(IndexError):
        project_cashflows(
            revenue=100.0,
            rev_growth=0.0,
            ebitda_margin=0.2,
            capex_pct=0.05,
            debt=50.0,
            interest_rate=0.1,
            tax_rate=0.25,
            years=2,
            debt_amort_schedule=[10.0],  # too short
        )
