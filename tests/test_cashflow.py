import pytest
from src.modules.cashflow import project_cashflows

def test_project_cashflows_basic():
    # Simple 2-year projection with no amortization
    results = project_cashflows(
        revenue=100.0,
        rev_growth=0.10,
        ebitda_margin=0.2,
        capex_pct=0.05,
        debt=50.0,
        interest_rate=0.1,
        tax_rate=0.25,
        years=2,
        debt_amort_schedule=[0.0, 0.0]
    )
    # Year 1 checks
    y1 = results["Year 1"]
    assert pytest.approx(y1["Revenue"], rel=1e-6) == 110.0
    assert pytest.approx(y1["EBITDA"], rel=1e-6) == 110.0 * 0.2
    assert pytest.approx(y1["CapEx"], rel=1e-6) == 110.0 * 0.05
    assert pytest.approx(y1["Interest"], rel=1e-6) == 50.0 * 0.1
    assert y1["Debt Amortized"] == 0.0
    assert y1["Ending Debt"] == 50.0

def test_project_cashflows_with_amortization():
    # 3-year projection with equal amortization
    results = project_cashflows(
        revenue=100.0,
        rev_growth=0.0,
        ebitda_margin=0.3,
        capex_pct=0.1,
        debt=90.0,
        interest_rate=0.05,
        tax_rate=0.2,
        years=3,
        debt_amort_schedule=[30.0, 30.0, 30.0]
    )
    # After full amortization, ending debt zero
    assert results["Year 3"]["Ending Debt"] == 0.0
