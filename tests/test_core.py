import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.lbo_model import LBOModel

def test_lbo_model_run():
    model = LBOModel(
        enterprise_value=100_000_000,
        debt_pct=0.6,
        revenue=50_000_000,
        rev_growth=0.10,
        ebitda_margin=0.20,
        capex_pct=0.05,
        exit_multiple=8.0,
        interest_rate=0.07
    )
    result = model.run(5)
    
    assert "Year 1" in result
    assert "Year 5" in result
    assert "Exit Summary" in result
    assert result["Exit Summary"]["IRR"] > 0
