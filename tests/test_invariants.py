import math

import pytest

from src.modules.fund_waterfall import compute_waterfall_by_year
from src.modules.lbo_model import InsolvencyError, LBOModel
from src.modules.orchestrator_advanced import (
    DealAssumptions,
    build_canonical_sources_and_uses,
    build_exit_equity_bridge,
    monte_carlo_analysis,
    run_enhanced_base_case,
)


def _small_model(**overrides):
    parameters = {
        "enterprise_value": 100.0,
        "debt_pct": 0.5,
        "senior_frac": 1.0,
        "mezz_frac": 0.0,
        "revenue": 20.0,
        "rev_growth": 0.0,
        "ebitda_margin": 0.5,
        "capex_pct": 0.0,
        "wc_pct": 0.0,
        "tax_rate": 0.0,
        "exit_multiple": 5.0,
        "senior_rate": 0.0,
        "mezz_rate": 0.0,
        "revolver_limit": 20.0,
        "revolver_rate": 0.0,
        "cash_sweep_pct": 0.0,
        "min_cash": 10.0,
        "opening_cash": 10.0,
        "initial_equity": 50.0,
    }
    parameters.update(overrides)
    return LBOModel(**parameters)


def test_sources_equal_uses():
    schedule = build_canonical_sources_and_uses(DealAssumptions())
    assert schedule["sources_equals_uses"]
    assert schedule["sources"]["Total Sources"] == pytest.approx(
        schedule["uses"]["Total Uses"]
    )


def test_base_case_debt_and_cash_roll_forwards_reconcile():
    assumptions = DealAssumptions()
    results, metrics = run_enhanced_base_case(assumptions)

    assert "Error" not in results
    assert metrics["Debt_Roll_Forward_Max_Delta"] < 1e-8
    assert metrics["Cash_Roll_Forward_Max_Delta"] < 1e-8

    for year in range(1, assumptions.years + 1):
        row = results[f"Year {year}"]
        assert (
            row["Opening Debt"]
            + row["Debt Draws"]
            + row["PIK Interest"]
            - row["Debt Repayments"]
        ) == pytest.approx(row["Closing Debt"])
        assert (
            row["Opening Cash"]
            + row["Operating Cash Generation"]
            + row["Operating Revolver Draw"]
            - row["Cash-Funded Amortization"]
            - row["Optional Cash Sweep"]
        ) == pytest.approx(row["Closing Cash"])


def test_revolver_funded_amortisation_reduces_target_debt():
    model = _small_model()
    senior = next(
        tranche for tranche in model.debt_tranches if tranche.name == "Senior"
    )
    senior.amort_schedule = [30.0]

    results = model.run(years=1)
    row = results["Year 1"]
    revolver = next(
        tranche for tranche in model.debt_tranches if tranche.revolver
    )

    assert row["Scheduled Amortization"] == pytest.approx(30.0)
    assert row["Cash-Funded Amortization"] == pytest.approx(10.0)
    assert row["Revolver-Funded Amortization"] == pytest.approx(20.0)
    assert row["Actual Amortization"] == pytest.approx(30.0)
    assert row["Ending Cash"] == pytest.approx(10.0)
    assert senior.balance == pytest.approx(20.0)
    assert revolver.balance == pytest.approx(20.0)
    assert row["Closing Debt"] == pytest.approx(40.0)


def test_operating_deficit_without_revolver_raises():
    model = _small_model(
        debt_pct=0.0,
        revolver_limit=0.0,
        revenue=10.0,
        ebitda_margin=0.0,
        capex_pct=2.0,
        initial_equity=100.0,
        opening_cash=0.0,
        min_cash=10.0,
    )
    with pytest.raises(InsolvencyError, match="no revolver"):
        model.run(years=1)


def test_insufficient_revolver_for_mandatory_principal_raises():
    model = _small_model(revolver_limit=5.0)
    senior = next(
        tranche for tranche in model.debt_tranches if tranche.name == "Senior"
    )
    senior.amort_schedule = [30.0]

    with pytest.raises(InsolvencyError, match="unpaid mandatory principal"):
        model.run(years=1)


def test_cash_is_not_distributed_and_retained_at_the_same_time():
    model = _small_model(
        debt_pct=0.0,
        revolver_limit=0.0,
        initial_equity=100.0,
        cash_sweep_pct=0.0,
    )
    results = model.run(years=2)

    assert results["Year 1"]["Equity CF"] == 0.0
    assert results["Year 2"]["Opening Cash"] == pytest.approx(
        results["Year 1"]["Ending Cash"]
    )


def test_exit_equity_includes_retained_cash():
    model = _small_model(
        debt_pct=0.0,
        revolver_limit=0.0,
        initial_equity=100.0,
        cash_sweep_pct=0.0,
        sale_cost_pct=0.01,
    )
    results = model.run(years=1)
    row = results["Year 1"]
    summary = results["Exit Summary"]

    expected = (
        row["EBITDA"] * 5.0
        - row["EBITDA"] * 5.0 * 0.01
        - row["Closing Debt"]
        + row["Ending Cash"]
    )
    assert summary["Equity Value"] == pytest.approx(expected)


def test_sponsor_equity_matches_initial_equity_cashflow():
    assumptions = DealAssumptions()
    schedule = build_canonical_sources_and_uses(assumptions)
    results, _ = run_enhanced_base_case(assumptions)
    vector = results["Exit Summary"]["Equity Cash Flow Vector"]

    assert vector[0] == pytest.approx(-schedule["equity_cheque"])


def test_exit_bridge_reconciles_to_model_metrics():
    assumptions = DealAssumptions()
    results, metrics = run_enhanced_base_case(assumptions)
    bridge = build_exit_equity_bridge(results, metrics, assumptions)

    assert bridge["exit_equity_value"] == pytest.approx(
        metrics["Equity Value"]
    )
    assert (
        bridge["exit_ev"]
        - bridge["sale_costs"]
        - bridge["final_debt"]
        + bridge["final_cash"]
    ) == pytest.approx(bridge["exit_equity_value"])


def test_preferred_return_compounds_and_carries_forward():
    required_distribution = 125.9712
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0, 0.0],
        distributions=[0.0, 0.0, required_distribution],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
    )
    final = waterfall[-1]

    assert final["LP Return of Capital"] == pytest.approx(100.0)
    assert final["Preferred Return Paid"] == pytest.approx(25.9712)
    assert final["Closing Accrued Preferred Return"] == pytest.approx(0.0)
    assert final["GP Carry Allocated"] == pytest.approx(0.0)
    assert final["LP Distributed"] == pytest.approx(required_distribution)


def test_management_fee_is_counted_once():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0],
        distributions=[120.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.02,
    )
    row = waterfall[0]

    assert row["Mgmt Fee"] == pytest.approx(2.0)
    assert row["Fund Cash Flow"] == pytest.approx(18.0)
    assert row["LP Cash Flow"] + row["GP Cash Flow"] == pytest.approx(18.0)


def test_cashless_carry_is_paid_once_in_final_year():
    waterfall = compute_waterfall_by_year(
        committed_capital=100.0,
        capital_calls=[100.0, 0.0, 0.0],
        distributions=[0.0, 0.0, 200.0],
        tiers=[{"rate": 0.08, "carry": 0.20}],
        gp_commitment=0.0,
        mgmt_fee_pct=0.0,
        cashless=True,
    )
    final = waterfall[-1]

    allocated = sum(row["GP Carry Allocated"] for row in waterfall)
    paid = sum(row["GP Carry Paid"] for row in waterfall)
    assert final["GP Final Pay"] == pytest.approx(allocated)
    assert paid == pytest.approx(allocated)
    assert final["GP Carry Deferred"] == pytest.approx(0.0)


def test_second_waterfall_tier_is_explicitly_unsupported():
    with pytest.raises(NotImplementedError):
        compute_waterfall_by_year(
            committed_capital=100.0,
            capital_calls=[100.0],
            distributions=[150.0],
            tiers=[
                {"rate": 0.08, "carry": 0.20},
                {"rate": 0.15, "carry": 0.30},
            ],
            mgmt_fee_pct=0.0,
        )


def test_monte_carlo_includes_every_scenario_in_unconditional_distribution():
    results = monte_carlo_analysis(DealAssumptions(), n=20, seed=7)

    assert results["Count"] == 20
    assert len(results["Scenarios"]) == 20
    assert len(results["IRRs"]) == 20
    assert results["Success_Rate"] == pytest.approx(
        results["Successful_Count"] / results["Count"]
    )
    assert math.isfinite(results["Median_IRR"])
