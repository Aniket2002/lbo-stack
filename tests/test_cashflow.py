import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.cashflow import project_cashflows

def test_project_cashflows_basic():
    result = project_cashflows(
        revenue=50_000_000,
        rev_growth=0.10,
        ebitda_margin=0.20,
        capex_pct=0.05,
        debt=60_000_000,
        interest_rate=0.07,
        years=1
    )

    year1 = result["Year 1"]
    assert round(year1["Revenue"]) == 55_000_000
    assert round(year1["EBITDA"]) == 11_000_000
    assert round(year1["CapEx"]) == 2_750_000
    assert round(year1["Interest"]) == 4_200_000
    assert round(year1["FCF"]) == 4_050_000
