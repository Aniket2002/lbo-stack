import pytest

from src.modules.fund_waterfall import (
    compute_waterfall_by_year,
    summarize_waterfall,
)
from src.modules.lbo_model import LBOModel


def test_distributions_reconcile_economically_each_year():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[20.0, 20.0, 20.0],
        distributions=[0.0, 25.0, 75.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )

    for row in waterfall:
        assert row["Gross Distribution Reconciliation"] == pytest.approx(
            row["Gross Dist"]
        )
        assert row["Gross Distribution Delta"] == pytest.approx(0.0)


def test_waterfall_summary_uses_final_cashflow_vectors():
    summary = summarize_waterfall(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0],
        distributions=[0.0, 150.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )

    assert "Net IRR (LP)" in summary
    assert "Fund IRR" in summary
    assert summary["MOIC"] > 1.0


def test_exit_proceeds_are_in_the_final_holding_period():
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=0.0,
        senior_frac=0.0,
        mezz_frac=0.0,
        revenue=100.0,
        rev_growth=0.0,
        ebitda_margin=0.20,
        capex_pct=0.0,
        wc_pct=0.0,
        tax_rate=0.0,
        exit_multiple=5.0,
        senior_rate=0.0,
        mezz_rate=0.0,
        da_pct=0.0,
        cash_sweep_pct=0.0,
        initial_equity=100.0,
        opening_cash=0.0,
    )

    results = model.run(years=5)
    vector = results["Exit Summary"]["Equity Cash Flow Vector"]

    assert len(vector) == 6
    assert vector[1:-1] == [0.0, 0.0, 0.0, 0.0]
    assert vector[-1] == pytest.approx(results["Exit Summary"]["Equity Value"])
