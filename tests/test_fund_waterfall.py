import pytest

from src.modules.fund_waterfall import (
    compute_waterfall_by_year,
    irr,
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
        assert row["Gross Distribution Reconciliation"] == pytest.approx(row["Gross Dist"])
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


def test_no_clawback_row_and_summary_cash_reporting_reconcile():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0],
        distributions=[0.0, 150.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    summary = summarize_waterfall(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0],
        distributions=[0.0, 150.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    final = waterfall[-1]

    assert final["Clawback"] == pytest.approx(0.0)
    assert final["LP Cash Flow"] == pytest.approx(
        -final["LP Called"] - final["LP Fee"] + final["LP Distributed"]
    )
    assert final["GP Cash Flow"] == pytest.approx(
        -final["GP Called"] - final["GP Fee"] + final["GP Distributed"]
    )
    assert summary["Cumulative LP Distributed"] == pytest.approx(final["Cumulative LP Distributed"])
    assert summary["Cumulative GP Cash Distributed"] == pytest.approx(
        final["Cumulative GP Cash Distributed"]
    )
    assert not summary["Clawback Triggered"]


def test_clawback_updates_final_row_cash_distributions_and_returns():
    kwargs = {
        "committed_capital": 100.0,
        "capital_calls": [10.0, 90.0],
        "distributions": [100.0, 0.0],
        "tiers": [{"rate": 0.08, "carry": 0.20}],
        "gp_commitment": 0.0,
        "mgmt_fee_pct": 0.0,
    }
    waterfall = compute_waterfall_by_year(**kwargs)
    summary = summarize_waterfall(**kwargs)
    final = waterfall[-1]

    assert final["Clawback"] > 0.0
    assert final["LP Distributed"] == pytest.approx(final["Clawback"])
    assert final["GP Distributed"] == pytest.approx(-final["Clawback"])
    assert final["LP Cash Flow"] == pytest.approx(
        -final["LP Called"] - final["LP Fee"] + final["LP Distributed"]
    )
    assert final["GP Cash Flow"] == pytest.approx(
        -final["GP Called"] - final["GP Fee"] + final["GP Distributed"]
    )
    assert final["Cumulative LP Distributed"] == pytest.approx(
        sum(row["LP Distributed"] for row in waterfall)
    )
    assert final["Cumulative GP Cash Distributed"] == pytest.approx(
        sum(row["GP Distributed"] for row in waterfall)
    )
    assert summary["Cumulative LP Distributed"] == pytest.approx(final["Cumulative LP Distributed"])
    assert summary["Cumulative GP Cash Distributed"] == pytest.approx(
        final["Cumulative GP Cash Distributed"]
    )
    assert summary["Clawback Amount"] == pytest.approx(final["Clawback"])
    assert summary["Net IRR (LP)"] == pytest.approx(final["LP IRR"])
    assert summary["Net IRR (GP)"] == pytest.approx(final["GP IRR"])
    assert summary["Fund IRR"] == pytest.approx(final["Fund IRR"])
    assert summary["MOIC"] == pytest.approx(final["MOIC"])
    assert final["LP IRR"] == pytest.approx(irr([row["LP Cash Flow"] for row in waterfall]))
    assert final["GP IRR"] == pytest.approx(irr([row["GP Cash Flow"] for row in waterfall]))
    assert final["Fund IRR"] == pytest.approx(irr([row["Fund Cash Flow"] for row in waterfall]))
    assert final["MOIC"] == pytest.approx(
        final["Cumulative LP Distributed"] / final["Cumulative LP Paid In"]
    )


def test_simple_interest_clawback_is_an_explicit_cash_transfer():
    no_interest = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[10.0, 90.0],
        distributions=[100.0, 0.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
    )
    with_interest = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[10.0, 90.0],
        distributions=[100.0, 0.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
        clawback_interest="simple",
    )
    final = with_interest[-1]

    assert final["Clawback"] == pytest.approx(no_interest[-1]["Clawback"] * (1.0 + 0.08 * 2))
    assert final["LP Clawback Receipt"] == pytest.approx(final["Clawback"])
    assert final["GP Clawback Payment"] == pytest.approx(final["Clawback"])
    assert sum(
        row["LP Distributed"] + row["GP Distributed"] for row in with_interest
    ) == pytest.approx(sum(row["Gross Dist"] for row in with_interest))


def test_waterfall_components_and_economic_distributions_reconcile():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0],
        distributions=[200.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
    )
    row = waterfall[0]

    assert row["LP Return of Capital"] > 0.0
    assert row["GP Return of Capital"] > 0.0
    assert row["Preferred Return Paid"] > 0.0
    assert row["Catch-up Paid"] > 0.0
    assert row["Residual LP"] > 0.0
    assert row["Residual GP"] > 0.0
    assert row["LP Economic Distribution"] == pytest.approx(
        row["LP Return of Capital"] + row["Preferred Return Paid"] + row["Residual LP"]
    )
    assert row["GP Economic Distribution"] == pytest.approx(
        row["GP Return of Capital"] + row["Catch-up Paid"] + row["Residual GP"]
    )
    assert row["LP Economic Distribution"] + row["GP Economic Distribution"] == pytest.approx(
        row["Gross Dist"]
    )


def test_cashless_carry_reserve_and_final_release_reconcile():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0, 0.0],
        distributions=[200.0, 0.0, 0.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
        cashless=True,
    )

    assert waterfall[0]["GP Carry Deferred"] > 0.0
    assert waterfall[0]["GP Distributed"] == pytest.approx(0.0)
    assert waterfall[-1]["GP Carry Reserve Release"] == pytest.approx(waterfall[-1]["GP Final Pay"])
    assert waterfall[-1]["GP Carry Deferred"] == pytest.approx(0.0)
    for row in waterfall:
        assert row["LP Distributed"] + row["GP Distributed"] == pytest.approx(
            row["Gross Dist"] - row["GP Carry Reserve Change"]
        )


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
