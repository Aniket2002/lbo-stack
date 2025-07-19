import pytest

from src.modules.cashflow import project_cashflows


def test_cashflow_projection_basic():
    result = project_cashflows(
        revenue=100.0,
        rev_growth=0.05,
        ebitda_margin=0.25,
        capex_pct=0.10,
        debt=60.0,
        interest_rate=0.05,
        tax_rate=0.30,
        years=3,
        debt_amort_schedule=[20.0, 20.0, 20.0],
    )
    assert len(result) == 3
    assert result["Year 1"]["EBITDA"] == pytest.approx(26.25, 0.1)


def test_zero_growth_and_no_amortization():
    output = project_cashflows(
        revenue=200.0,
        rev_growth=0.0,
        ebitda_margin=0.3,
        capex_pct=0.05,
        debt=50.0,
        interest_rate=0.04,
        tax_rate=0.25,
        years=2,
        debt_amort_schedule=None,
    )
    assert output["Year 1"]["Revenue"] == output["Year 2"]["Revenue"]
    assert output["Year 2"]["Ending Debt"] == pytest.approx(50.0)
