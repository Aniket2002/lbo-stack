import pytest

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall


def test_waterfall_simple_no_carry():
    # Single-year, zero carry
    committed = 100.0
    calls = [100.0]
    dists = [120.0]
    tiers = [{"hurdle": 0.0, "carry": 0.0}]
    wf = compute_waterfall_by_year(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    assert len(wf) == 1
    assert wf[0]["LP Share"] == pytest.approx(120.0)

    summary = summarize_waterfall(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    assert summary["Net IRR (LP)"] >= 0.0
    assert summary["MOIC"] == pytest.approx(1.2)


def test_waterfall_clawback():
    # GP overpaid scenario triggers clawback
    committed = 100.0
    calls = [50.0, 50.0]
    dists = [200.0, 0.0]
    tiers = [{"hurdle": 0.0, "carry": 1.0}]
    wf = compute_waterfall_by_year(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.0,
    )
    # Last row contains a Clawback column when triggered
    assert any("Clawback" in key for key in wf[-1].keys())

    summary = summarize_waterfall(
        committed_capital=committed,
        capital_calls=calls,
        distributions=dists,
        tiers=tiers,
        gp_commitment=0.0,
    )
    assert summary["Clawback Triggered"] is True
