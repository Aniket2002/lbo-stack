import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from modules.fund_waterfall import summarize_waterfall

def test_basic_fund_summary():
    summary = summarize_waterfall(
        committed_capital=100_000_000,
        capital_calls=[30e6, 30e6, 20e6, 10e6, 0],
        distributions=[0, 0, 0, 0, 160e6],
        tiers=[{"hurdle": 0.08, "carry": 0.2}, {"hurdle": 0.12, "carry": 0.3}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.02,
        reset_hurdle=False,
        cashless=False
    )
    assert summary["Gross IRR"] > 0
    assert "Clawback Triggered" in summary
