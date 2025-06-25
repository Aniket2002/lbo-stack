# tests/test_fund_waterfall.py

import pytest

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall


def test_waterfall_simple_no_carry():
    # Single-year, zero carry
    committed = 100.0
    calls = [100.0]
    dists = [120.0]
    tiers = [{"type": "irr", "rate": 0.0, "carry": 0.0}]
    wf = compute_waterfall_by_year(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    # One row, LP gets entire distribution
    assert len(wf) == 1
    assert wf[0]["LP Distributed"] == pytest.approx(120.0)
    assert wf[0]["GP Paid"] == pytest.approx(0.0)

    summary = summarize_waterfall(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    assert summary["Net IRR (LP)"] >= 0.0
    assert summary["MOIC"] == pytest.approx(120.0 / (100.0 * (1 - 0.02)))


def test_waterfall_cashless_and_final_payout_and_clawback():
    # Cashless mode: accrue in year 1, pay in final year, no clawback
    wf = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[50.0, 50.0],
        distributions=[200.0, 0.0],
        tiers=[{"type": "irr", "rate": 0.0, "carry": 1.0}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
        cashless=True,
    )
    # Year 1: all distributions accrue to GP after LP getback
    assert wf[0]["GP Paid"] == pytest.approx(0.0)
    assert wf[0]["GP Accrued"] == pytest.approx(150.0)

    # Final year: GP Final Pay equals accrued amount
    assert "GP Final Pay" in wf[-1]
    assert wf[-1]["GP Final Pay"] == pytest.approx(wf[0]["GP Accrued"])

    # No clawback should ever appear
    assert "Clawback" not in wf[-1]

    summary = summarize_waterfall(
        committed_capital=100.0,
        capital_calls=[50.0, 50.0],
        distributions=[200.0, 0.0],
        tiers=[{"type": "irr", "rate": 0.0, "carry": 1.0}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
        cashless=True,
    )
    assert summary["Clawback Triggered"] is False
