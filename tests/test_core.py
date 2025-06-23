import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from modules.lbo_model import LBOModel

def test_basic_lbo_run():
    model = LBOModel(
        enterprise_value=100_000_000,
        debt_pct=0.6,
        revenue=50_000_000,
        rev_growth=0.1,
        ebitda_margin=0.2,
        capex_pct=0.05,
        wc_pct=0.1,
        tax_rate=0.25,
        exit_multiple=8.0,
        interest_rate=0.07
    )
    results = model.run(years=5, use_sweep=False)
    assert "Exit Summary" in results
    assert results["Exit Summary"]["IRR"] > 0
