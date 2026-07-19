from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fpdf import FPDF

try:
    from .fund_waterfall import compute_waterfall_by_year, summarize_waterfall
    from .lbo_model import (
        CovenantBreachError,
        DebtTranche,
        InsolvencyError,
        LBOModel,
    )
except ImportError:  # pragma: no cover - direct script execution
    from fund_waterfall import compute_waterfall_by_year, summarize_waterfall
    from lbo_model import (
        CovenantBreachError,
        DebtTranche,
        InsolvencyError,
        LBOModel,
    )

plt.switch_backend("Agg")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"

MONTE_CARLO_PRIORS_DEFAULT: Dict[str, float] = {
    "growth_sigma": 0.03,
    "margin_sigma": 0.015,
    "multiple_sigma": 0.75,
    "growth_floor": -0.05,
    "margin_floor": 0.08,
    "multiple_floor": 4.0,
}


@dataclass
class DealAssumptions:
    # Entry and exit
    entry_ev_ebitda: float = 8.5
    exit_ev_ebitda: float = 10.0
    debt_pct_of_ev: float = 0.60
    sale_cost_pct: float = 0.01
    entry_fees_pct: float = 0.02
    financing_fee_pct: float = 0.015
    senior_oid_pct: float = 0.005

    # Operating case
    revenue0: float = 5_000.0
    rev_growth_geo: float = 0.04
    ebitda_margin_start: float = 0.22
    ebitda_margin_end: float = 0.25
    maintenance_capex_pct: float = 0.025
    growth_capex_pct: float = 0.015
    da_pct_of_revenue: float = 0.03
    tax_rate: float = 0.25

    # Working capital days
    days_receivables: float = 15.0
    days_payables: float = 30.0
    days_deferred_revenue: float = 20.0

    # Financial debt
    senior_frac: float = 0.70
    mezz_frac: float = 0.20
    senior_rate: float = 0.045
    mezz_rate: float = 0.08
    pik_rate: float = 0.0
    senior_amort_pct: float = 0.01
    mezz_amort_pct: float = 0.0
    revolver_limit: float = 200.0
    revolver_rate: float = 0.04
    cash_sweep_pct: float = 0.85
    min_cash: float = 150.0

    # Covenants
    icr_hurdle: Optional[float] = 1.80
    leverage_hurdle: Optional[float] = 9.0
    fcf_hurdle: Optional[float] = 1.05

    # Horizon
    years: int = 5

    # Simplified IFRS-16 treatment
    ifrs16_method: str = "lease_in_debt"
    lease_liability_mult_of_ebitda: float = 3.2
    lease_rate: float = 0.045
    lease_amort_years: int = 15


def get_output_path(filename: str) -> str:  # pragma: no cover
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT_DIR / filename)


def build_canonical_sources_and_uses(a: DealAssumptions) -> Dict[str, Any]:
    """Build the single transaction-entry schedule used by the model."""
    ebitda0 = a.revenue0 * a.ebitda_margin_start
    enterprise_value = a.entry_ev_ebitda * ebitda0
    total_financial_debt = enterprise_value * a.debt_pct_of_ev

    senior_debt = total_financial_debt * a.senior_frac
    mezz_debt = total_financial_debt * a.mezz_frac
    bullet_debt = max(
        0.0,
        total_financial_debt - senior_debt - mezz_debt,
    )

    purchase_price = enterprise_value
    transaction_fees = enterprise_value * a.entry_fees_pct
    financing_fees = total_financial_debt * a.financing_fee_pct
    oid = senior_debt * a.senior_oid_pct
    retained_cash = a.min_cash

    total_uses = (
        purchase_price
        + transaction_fees
        + financing_fees
        + oid
        + retained_cash
    )
    sponsor_equity = total_uses - total_financial_debt

    sources = {
        "Senior Debt": senior_debt,
        "Mezzanine Debt": mezz_debt,
        "Bullet Debt": bullet_debt,
        "Sponsor Equity": sponsor_equity,
        "Total Sources": total_financial_debt + sponsor_equity,
    }
    uses = {
        "Purchase Price": purchase_price,
        "Transaction Fees": transaction_fees,
        "Financing Fees": financing_fees,
        "OID": oid,
        "Retained Cash": retained_cash,
        "Total Uses": total_uses,
    }

    lease_liability = ebitda0 * a.lease_liability_mult_of_ebitda
    return {
        "enterprise_value": enterprise_value,
        "ebitda0": ebitda0,
        "sources": sources,
        "uses": uses,
        "financial_debt_sources": total_financial_debt,
        "equity_cheque": sponsor_equity,
        "opening_cash": retained_cash,
        "sources_equals_uses": math.isclose(
            sources["Total Sources"],
            uses["Total Uses"],
            rel_tol=0.0,
            abs_tol=1e-8,
        ),
        "ifrs16": {
            "liability": lease_liability,
            "treated_as_assumed_liability": True,
            "not_a_cash_source": True,
        },
        "memo": {"revolver_capacity": a.revolver_limit},
    }


def build_sources_and_uses(a: DealAssumptions) -> Dict[str, Any]:  # pragma: no cover
    return build_canonical_sources_and_uses(a)


def build_sources_and_uses_micro_graphic(  # pragma: no cover
    a: DealAssumptions,
) -> Dict[str, Any]:
    return build_canonical_sources_and_uses(a)


def calculate_days_based_wc(revenue: float, a: DealAssumptions) -> float:
    daily_revenue = revenue / 365.0
    receivables = daily_revenue * a.days_receivables
    payables = daily_revenue * a.days_payables
    deferred_revenue = daily_revenue * a.days_deferred_revenue
    return receivables - payables - deferred_revenue


def build_revenue_growth_schedule(a: DealAssumptions) -> list[float]:
    return [a.rev_growth_geo] * a.years


def build_ebitda_margin_schedule(a: DealAssumptions) -> list[float]:
    if a.years <= 1:
        return [a.ebitda_margin_end]
    return np.linspace(
        a.ebitda_margin_start,
        a.ebitda_margin_end,
        a.years,
    ).tolist()


def _projected_revenues(a: DealAssumptions) -> list[float]:
    revenue = a.revenue0
    revenues: list[float] = []
    for growth in build_revenue_growth_schedule(a):
        revenue *= 1.0 + growth
        revenues.append(revenue)
    return revenues


def build_capex_schedule(a: DealAssumptions) -> list[float]:
    capex_rate = a.maintenance_capex_pct + a.growth_capex_pct
    return [revenue * capex_rate for revenue in _projected_revenues(a)]


def build_da_schedule(a: DealAssumptions) -> list[float]:
    return [
        revenue * a.da_pct_of_revenue
        for revenue in _projected_revenues(a)
    ]


def build_wc_schedule(a: DealAssumptions) -> list[float]:
    previous_wc = calculate_days_based_wc(a.revenue0, a)
    schedule: list[float] = []
    for revenue in _projected_revenues(a):
        current_wc = calculate_days_based_wc(revenue, a)
        schedule.append(current_wc - previous_wc)
        previous_wc = current_wc
    return schedule


def build_enhanced_lbo_config(a: DealAssumptions) -> Dict[str, Any]:
    canonical = build_canonical_sources_and_uses(a)
    return {
        "enterprise_value": canonical["enterprise_value"],
        "debt_pct": (
            canonical["financial_debt_sources"]
            / canonical["enterprise_value"]
        ),
        "senior_frac": a.senior_frac,
        "mezz_frac": a.mezz_frac,
        "revenue": a.revenue0,
        "rev_growth": a.rev_growth_geo,
        "ebitda_margin": a.ebitda_margin_start,
        "ebitda_margin_end": a.ebitda_margin_end,
        "capex_pct": a.maintenance_capex_pct + a.growth_capex_pct,
        "wc_pct": 0.0,
        "tax_rate": a.tax_rate,
        "exit_multiple": a.exit_ev_ebitda,
        "senior_rate": a.senior_rate,
        "mezz_rate": a.mezz_rate,
        "revolver_limit": a.revolver_limit,
        "revolver_rate": a.revolver_rate,
        "pik_rate": a.pik_rate,
        "ltv_hurdle": None,
        "icr_hurdle": a.icr_hurdle,
        "da_pct": a.da_pct_of_revenue,
        "cash_sweep_pct": a.cash_sweep_pct,
        "min_cash": a.min_cash,
        "sale_cost_pct": a.sale_cost_pct,
        "revenue_growth_schedule": build_revenue_growth_schedule(a),
        "ebitda_margin_schedule": build_ebitda_margin_schedule(a),
        "capex_schedule": build_capex_schedule(a),
        "da_schedule": build_da_schedule(a),
        "wc_schedule": build_wc_schedule(a),
        "initial_equity": canonical["equity_cheque"],
        "opening_cash": canonical["opening_cash"],
    }


def apply_financial_debt_amortisation(
    model: LBOModel,
    a: DealAssumptions,
) -> None:
    for tranche in model.debt_tranches:
        if tranche.name == "Senior":
            annual = tranche.orig_balance * a.senior_amort_pct
            tranche.amort_schedule = [annual] * a.years
        elif tranche.name == "Mezzanine":
            annual = tranche.orig_balance * a.mezz_amort_pct
            tranche.amort_schedule = [annual] * a.years


def add_ifrs16_lease_tranche(model: LBOModel, a: DealAssumptions) -> None:
    if a.ifrs16_method != "lease_in_debt":
        return
    if a.lease_amort_years <= 0:
        raise ValueError("lease_amort_years must be positive")

    opening_ebitda = a.revenue0 * a.ebitda_margin_start
    lease_balance = a.lease_liability_mult_of_ebitda * opening_ebitda
    annual_principal = lease_balance / a.lease_amort_years
    lease = DebtTranche(
        name="IFRS16 Leases",
        balance=lease_balance,
        rate=a.lease_rate,
        amort=True,
        sweepable=False,
        amort_schedule=[annual_principal] * a.years,
    )
    model.debt_tranches.insert(0, lease)


def _safe_min(values: list[float], default: float = math.nan) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return min(finite) if finite else default


def run_enhanced_base_case(
    a: DealAssumptions,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    model = LBOModel(**build_enhanced_lbo_config(a))
    apply_financial_debt_amortisation(model, a)
    add_ifrs16_lease_tranche(model, a)

    try:
        results = model.run(years=a.years)
    except (CovenantBreachError, InsolvencyError) as exc:
        return {
            "Error": str(exc),
        }, {
            "IRR": math.nan,
            "MOIC": math.nan,
            "Equity Value": math.nan,
            "Error": str(exc),
        }

    metrics: Dict[str, Any] = dict(results["Exit Summary"])
    icr_series: list[float] = []
    leverage_series: list[float] = []
    fcf_coverage_series: list[float] = []
    debt_deltas: list[float] = []
    cash_deltas: list[float] = []

    for year in range(1, a.years + 1):
        row = results[f"Year {year}"]
        ebitda = row["EBITDA"]
        cash_interest = row["Cash Interest"]
        total_debt = row["Closing Debt"]
        ending_cash = row["Ending Cash"]
        net_debt = total_debt - ending_cash

        icr = math.inf if cash_interest <= 1e-12 else ebitda / cash_interest
        leverage = net_debt / ebitda if ebitda > 0 else math.inf
        debt_service = cash_interest + row["Actual Amortization"]
        pre_debt_service_cash = (
            row["Operating Cash Generation"] + cash_interest
        )
        fcf_coverage = (
            pre_debt_service_cash / debt_service
            if debt_service > 1e-12
            else math.inf
        )

        icr_series.append(icr)
        leverage_series.append(leverage)
        fcf_coverage_series.append(fcf_coverage)
        debt_deltas.append(abs(row["Debt Roll-Forward Delta"]))
        cash_deltas.append(abs(row["Cash Roll-Forward Delta"]))

    min_icr = _safe_min(icr_series, math.inf)
    max_leverage = max(leverage_series)
    min_fcf_coverage = _safe_min(fcf_coverage_series, math.inf)

    metrics.update(
        {
            "ICR_Series": icr_series,
            "Leverage_Series": leverage_series,
            "LTV_Series": leverage_series,
            "FCF_Coverage_Series": fcf_coverage_series,
            "Min_ICR": min_icr,
            "Max_Leverage": max_leverage,
            "Max_LTV": max_leverage,
            "Min_FCF_Coverage": min_fcf_coverage,
            "ICR_Headroom": (
                min_icr - a.icr_hurdle
                if a.icr_hurdle is not None
                else math.nan
            ),
            "Leverage_Headroom": (
                a.leverage_hurdle - max_leverage
                if a.leverage_hurdle is not None
                else math.nan
            ),
            "FCF_Headroom": (
                min_fcf_coverage - a.fcf_hurdle
                if a.fcf_hurdle is not None
                else math.nan
            ),
            "ICR_Breach": (
                a.icr_hurdle is not None and min_icr < a.icr_hurdle
            ),
            "Leverage_Breach": (
                a.leverage_hurdle is not None
                and max_leverage > a.leverage_hurdle
            ),
            "LTV_Breach": (
                a.leverage_hurdle is not None
                and max_leverage > a.leverage_hurdle
            ),
            "FCF_Breach": (
                a.fcf_hurdle is not None
                and min_fcf_coverage < a.fcf_hurdle
            ),
            "Debt_Roll_Forward_Max_Delta": max(debt_deltas, default=0.0),
            "Cash_Roll_Forward_Max_Delta": max(cash_deltas, default=0.0),
            "Sources_Equals_Uses": build_canonical_sources_and_uses(a)[
                "sources_equals_uses"
            ],
        }
    )
    return results, metrics


def build_exit_equity_bridge(
    results: Dict[str, Any],
    metrics: Dict[str, Any],
    a: DealAssumptions,
) -> Dict[str, Any]:
    final_year = results[f"Year {a.years}"]

    final_ebitda = float(final_year["EBITDA"])
    exit_ev = final_ebitda * a.exit_ev_ebitda
    sale_costs = exit_ev * a.sale_cost_pct
    final_debt = float(final_year["Closing Debt"])
    final_cash = float(final_year["Ending Cash"])

    exit_equity_value = (
        exit_ev
        - sale_costs
        - final_debt
        + final_cash
    )

    raw_metric_equity = metrics.get("Equity Value", math.nan)
    metric_equity = (
        float(raw_metric_equity)
        if raw_metric_equity is not None
        else math.nan
    )

    if math.isfinite(metric_equity) and not math.isclose(
        exit_equity_value,
        metric_equity,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise AssertionError(
            "Exit bridge does not reconcile to model metrics: "
            f"bridge={exit_equity_value:.8f}, "
            f"model={metric_equity:.8f}"
        )

    return {
        "final_ebitda": final_ebitda,
        "exit_multiple": a.exit_ev_ebitda,
        "exit_ev": exit_ev,
        "sale_costs": sale_costs,
        "final_net_debt": final_debt - final_cash,
        "final_debt": final_debt,
        "final_cash": final_cash,
        "exit_equity_value": exit_equity_value,
        "moic": metrics.get("MOIC", math.nan),
        "irr": metrics.get("IRR", math.nan),
    }


def build_exit_equity_bridge_micro_graphic(
    results: Dict[str, Any],
    metrics: Dict[str, Any],
    a: DealAssumptions,
) -> Dict[str, Any]:
    bridge: Dict[str, Any] = build_exit_equity_bridge(
        results,
        metrics,
        a,
    )

    bridge["bridge_steps"] = [
        {
            "step": "Final EBITDA",
            "value": bridge["final_ebitda"],
        },
        {
            "step": "Exit multiple",
            "value": bridge["exit_multiple"],
        },
        {
            "step": "Enterprise value",
            "value": bridge["exit_ev"],
        },
        {
            "step": "Less sale costs",
            "value": -bridge["sale_costs"],
        },
        {
            "step": "Less debt",
            "value": -bridge["final_debt"],
        },
        {
            "step": "Add cash",
            "value": bridge["final_cash"],
        },
        {
            "step": "Equity value",
            "value": bridge["exit_equity_value"],
        },
    ]

    return bridge


def build_deleveraging_walk(  # pragma: no cover
    results: Dict[str, Any],
    a: DealAssumptions,
) -> Dict[str, Any]:
    rows = []
    for year in range(1, a.years + 1):
        row = results[f"Year {year}"]
        net_debt = row["Closing Debt"] - row["Ending Cash"]
        leverage = net_debt / row["EBITDA"]
        rows.append(
            {
                "year": year,
                "ebitda": row["EBITDA"],
                "gross_debt": row["Closing Debt"],
                "cash": row["Ending Cash"],
                "net_debt": net_debt,
                "net_debt_ebitda": leverage,
            }
        )
    return {
        "leverage_walk": rows,
        "starting_leverage": rows[0]["net_debt_ebitda"],
        "ending_leverage": rows[-1]["net_debt_ebitda"],
        "total_deleveraging": (
            rows[0]["net_debt_ebitda"]
            - rows[-1]["net_debt_ebitda"]
        ),
    }


def build_deleveraging_walk_micro_graphic(  # pragma: no cover
    results: Dict[str, Any],
    a: DealAssumptions,
) -> Dict[str, Any]:
    return build_deleveraging_walk(results, a)


def validate_irr_cashflows(  # pragma: no cover
    results: Dict[str, Any],
    a: DealAssumptions,
) -> Dict[str, Any]:
    vector = results["Exit Summary"]["Equity Cash Flow Vector"]
    return {
        "initial_negative": bool(vector and vector[0] < 0),
        "has_positive_inflow": any(value > 0 for value in vector[1:]),
        "final_year_positive": bool(vector and vector[-1] > 0),
        "cashflow_series": vector,
        "period_count_correct": len(vector) == a.years + 1,
    }


def enhanced_sensitivity_grid(a: DealAssumptions) -> pd.DataFrame:  # pragma: no cover
    exit_multiples = [
        a.exit_ev_ebitda - 1.0,
        a.exit_ev_ebitda,
        a.exit_ev_ebitda + 1.0,
    ]
    margin_deltas = [-0.04, 0.0, 0.04]
    records = []

    for margin_delta in margin_deltas:
        for exit_multiple in exit_multiples:
            case = DealAssumptions(
                **{
                    **a.__dict__,
                    "exit_ev_ebitda": exit_multiple,
                    "ebitda_margin_start": (
                        a.ebitda_margin_start + margin_delta
                    ),
                    "ebitda_margin_end": (
                        a.ebitda_margin_end + margin_delta
                    ),
                }
            )
            _, metrics = run_enhanced_base_case(case)
            records.append(
                {
                    "Terminal Margin": case.ebitda_margin_end,
                    "Exit Multiple": exit_multiple,
                    "IRR": metrics.get("IRR", math.nan),
                }
            )

    frame = pd.DataFrame(records)
    return frame.pivot(
        index="Terminal Margin",
        columns="Exit Multiple",
        values="IRR",
    )


def monte_carlo_analysis(
    a: DealAssumptions,
    n: int = 500,
    seed: int = 42,
    priors: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    if n <= 0:
        raise ValueError("n must be positive")

    assumptions = {**MONTE_CARLO_PRIORS_DEFAULT, **(priors or {})}
    rng = np.random.default_rng(seed)
    scenario_records = []
    unconditional_irrs: list[float] = []
    successful_irrs: list[float] = []
    breach_count = 0
    insolvency_count = 0
    negative_equity_count = 0
    capital_loss_count = 0

    for scenario_id in range(1, n + 1):
        exit_multiple = max(
            assumptions["multiple_floor"],
            rng.normal(a.exit_ev_ebitda, assumptions["multiple_sigma"]),
        )
        ending_margin = max(
            assumptions["margin_floor"],
            rng.normal(a.ebitda_margin_end, assumptions["margin_sigma"]),
        )
        growth = max(
            assumptions["growth_floor"],
            rng.normal(a.rev_growth_geo, assumptions["growth_sigma"]),
        )

        scenario = DealAssumptions(
            **{
                **a.__dict__,
                "exit_ev_ebitda": float(exit_multiple),
                "ebitda_margin_end": float(ending_margin),
                "rev_growth_geo": float(growth),
            }
        )
        projections, metrics = run_enhanced_base_case(scenario)
        error = projections.get("Error")

        if error:
            irr_value = -1.0
            equity_value = 0.0
            breached = "breach" in error.lower()
            insolvent = "cash" in error.lower() or "principal" in error.lower()
        else:
            raw_irr = metrics.get("IRR")
            irr_value = -1.0 if raw_irr is None else float(raw_irr)
            equity_value = float(metrics.get("Equity Value", 0.0))
            breached = bool(
                metrics.get("ICR_Breach")
                or metrics.get("Leverage_Breach")
            )
            insolvent = False

        negative_equity = equity_value < 0
        capital_loss = negative_equity or irr_value < 0
        success = (
            not breached
            and not insolvent
            and not negative_equity
            and irr_value >= 0.08
        )

        unconditional_irrs.append(irr_value)
        if success:
            successful_irrs.append(irr_value)
        breach_count += int(breached)
        insolvency_count += int(insolvent)
        negative_equity_count += int(negative_equity)
        capital_loss_count += int(capital_loss)

        scenario_records.append(
            {
                "Scenario": scenario_id,
                "Seed": seed,
                "Exit Multiple": float(exit_multiple),
                "Ending Margin": float(ending_margin),
                "Growth": float(growth),
                "IRR": irr_value,
                "Equity Value": equity_value,
                "Breached": breached,
                "Insolvent": insolvent,
                "Negative Equity": negative_equity,
                "Capital Loss": capital_loss,
                "Successful": success,
                "Error": error or "",
            }
        )

    return {
        "Seed": seed,
        "Scenarios": scenario_records,
        "IRRs": unconditional_irrs,
        "Successful_IRRs": successful_irrs,
        "Count": n,
        "N": n,
        "Successful_Count": len(successful_irrs),
        "Breaches": breach_count,
        "Insolvent": insolvency_count,
        "Negative_Equity": negative_equity_count,
        "Capital_Loss": capital_loss_count,
        "Success_Rate": len(successful_irrs) / n,
        "Breach_Frequency": breach_count / n,
        "Insolvency_Frequency": insolvency_count / n,
        "Capital_Loss_Frequency": capital_loss_count / n,
        "Median_IRR": float(np.median(unconditional_irrs)),
        "P10_IRR": float(np.percentile(unconditional_irrs, 10)),
        "P90_IRR": float(np.percentile(unconditional_irrs, 90)),
        "Std_IRR": float(np.std(unconditional_irrs)),
        "Median_Success_IRR": (
            float(np.median(successful_irrs))
            if successful_irrs
            else math.nan
        ),
        "Priors": {
            "growth_sigma": assumptions["growth_sigma"],
            "margin_sigma": assumptions["margin_sigma"],
            "multiple_sigma": assumptions["multiple_sigma"],
        },
        "SuccessDef": (
            "No covenant breach or insolvency, positive exit equity, "
            "and IRR >= 8%"
        ),
    }


def build_monte_carlo_projections(a: DealAssumptions) -> Dict[str, Any]:  # pragma: no cover
    rng = np.random.default_rng(42)
    base_ebitda = a.revenue0 * a.ebitda_margin_start
    scenarios = []
    for _ in range(100):
        current = base_ebitda
        path = []
        for year in range(1, a.years + 1):
            target = base_ebitda * (1.0 + a.rev_growth_geo) ** year
            current = 0.8 * current + 0.2 * target + rng.normal(
                0.0,
                base_ebitda * 0.10,
            )
            path.append(max(current, base_ebitda * 0.30))
        scenarios.append(path)

    array = np.asarray(scenarios)
    return {
        "scenarios": scenarios[:20],
        "percentiles": {
            "p10": np.percentile(array, 10, axis=0).tolist(),
            "p50": np.percentile(array, 50, axis=0).tolist(),
            "p90": np.percentile(array, 90, axis=0).tolist(),
        },
        "summary": {"scenarios_run": len(scenarios)},
    }


def build_monte_carlo_footer(mc_results: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
    priors = mc_results["Priors"]
    return {
        "priors_used": priors,
        "success_definition": mc_results["SuccessDef"],
        "results_summary": {
            "median_irr": mc_results["Median_IRR"],
            "p10_irr": mc_results["P10_IRR"],
            "p90_irr": mc_results["P90_IRR"],
            "success_rate": mc_results["Success_Rate"],
            "total_paths": mc_results["Count"],
        },
    }


def get_recruiter_ready_narrative(  # pragma: no cover
    metrics: Dict[str, Any],
    a: DealAssumptions,
    mc_results: Optional[Dict[str, Any]] = None,
) -> str:
    mc_results = mc_results or {}
    irr = metrics.get("IRR")
    irr_text = "n/a" if irr is None else f"{irr:.1%}"
    return (
        "The current assumption-driven LBO scenario produces "
        f"{irr_text} IRR and {metrics.get('MOIC', math.nan):.2f}x MOIC. "
        "The model separately tracks cash and PIK interest, minimum-cash "
        "funding, mandatory amortisation, revolver usage, cash sweeps, "
        "covenants and exit-equity reconciliation."
    )


def run_comprehensive_lbo_analysis(a: DealAssumptions) -> Dict[str, Any]:  # pragma: no cover
    results, metrics = run_enhanced_base_case(a)
    if "Error" in results:
        return {"error": results["Error"]}

    canonical = build_canonical_sources_and_uses(a)
    initial_equity = canonical["equity_cheque"]
    exit_distribution = metrics["Equity Value"]
    calls = [initial_equity] + [0.0] * (a.years - 1)
    distributions = [0.0] * (a.years - 1) + [exit_distribution]

    fund_results = compute_waterfall_by_year(
        committed_capital=initial_equity,
        capital_calls=calls,
        distributions=distributions,
        tiers=[{"type": "irr", "rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
        cashless=False,
    )
    fund_summary = summarize_waterfall(
        committed_capital=initial_equity,
        capital_calls=calls,
        distributions=distributions,
        tiers=[{"type": "irr", "rate": 0.08, "carry": 0.20}],
        gp_commitment=0.02,
        mgmt_fee_pct=0.0,
        cashless=False,
    )

    sensitivity = enhanced_sensitivity_grid(a)
    monte_carlo = monte_carlo_analysis(a, n=400, seed=42)

    return {
        "financial_projections": results,
        "metrics": metrics,
        "sources_and_uses": canonical,
        "exit_bridge": build_exit_equity_bridge(results, metrics, a),
        "deleveraging": build_deleveraging_walk(results, a),
        "fund_waterfall": fund_results,
        "fund_summary": fund_summary,
        "sensitivity_analysis": sensitivity,
        "monte_carlo_results": monte_carlo,
        "monte_carlo": build_monte_carlo_projections(a),
        "mc_footer": build_monte_carlo_footer(monte_carlo),
        "irr_validation": validate_irr_cashflows(results, a),
        "narrative": get_recruiter_ready_narrative(metrics, a, monte_carlo),
        "assumptions": a,
    }


def plot_covenant_headroom(  # pragma: no cover
    metrics: Dict[str, Any],
    a: DealAssumptions,
    out_path: Optional[str] = None,
):
    years = list(range(1, len(metrics["ICR_Series"]) + 1))
    fig, axes = plt.subplots(3, 1, figsize=(9, 10))

    axes[0].plot(years, metrics["ICR_Series"], marker="o")
    if a.icr_hurdle is not None:
        axes[0].axhline(a.icr_hurdle, linestyle="--")
    axes[0].set_title("Cash Interest Coverage")
    axes[0].set_ylabel("EBITDA / cash interest")

    axes[1].plot(years, metrics["Leverage_Series"], marker="o")
    if a.leverage_hurdle is not None:
        axes[1].axhline(a.leverage_hurdle, linestyle="--")
    axes[1].set_title("Net Debt / EBITDA")
    axes[1].set_ylabel("Multiple")

    axes[2].plot(years, metrics["FCF_Coverage_Series"], marker="o")
    if a.fcf_hurdle is not None:
        axes[2].axhline(a.fcf_hurdle, linestyle="--")
    axes[2].set_title("Cash-flow Coverage")
    axes[2].set_xlabel("Year")
    axes[2].set_ylabel("Multiple")

    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return fig


def plot_deleveraging_path(  # pragma: no cover
    results: Dict[str, Any],
    a: DealAssumptions,
    out_path: Optional[str] = None,
):
    walk = build_deleveraging_walk(results, a)["leverage_walk"]
    frame = pd.DataFrame(walk)
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.plot(frame["year"], frame["net_debt"], marker="o", label="Net debt")
    axis.plot(frame["year"], frame["ebitda"], marker="o", label="EBITDA")
    axis.set_title("Deleveraging Path")
    axis.set_xlabel("Year")
    axis.set_ylabel("Model currency units")
    axis.legend()
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return fig


def plot_exit_equity_bridge(  # pragma: no cover
    results: Dict[str, Any],
    metrics: Dict[str, Any],
    a: DealAssumptions,
    out_path: Optional[str] = None,
):
    bridge = build_exit_equity_bridge(results, metrics, a)
    labels = ["Exit EV", "Sale costs", "Debt", "Cash", "Equity"]
    values = [
        bridge["exit_ev"],
        -bridge["sale_costs"],
        -bridge["final_debt"],
        bridge["final_cash"],
        bridge["exit_equity_value"],
    ]
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.bar(labels, values)
    axis.set_title("Exit Equity Bridge")
    axis.set_ylabel("Model currency units")
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return fig


def plot_sources_and_uses(  # pragma: no cover
    a: DealAssumptions,
    out_path: Optional[str] = None,
):
    schedule = build_canonical_sources_and_uses(a)
    sources = {
        key: value
        for key, value in schedule["sources"].items()
        if key != "Total Sources"
    }
    uses = {
        key: value
        for key, value in schedule["uses"].items()
        if key != "Total Uses"
    }

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(sources.keys(), sources.values())
    axes[0].set_title("Sources")
    axes[0].tick_params(axis="x", rotation=45)
    axes[1].bar(uses.keys(), uses.values())
    axes[1].set_title("Uses")
    axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return fig


def plot_sensitivity_heatmap(
    sensitivity: pd.DataFrame,
    out_path: Optional[str] = None,
):
    display = sensitivity.astype(float) * 100.0

    fig, axis = plt.subplots(figsize=(8, 5))
    image = axis.imshow(
        display.to_numpy(dtype=float),
        aspect="auto",
    )

    axis.set_xticks(range(len(display.columns)))
    axis.set_xticklabels(
        [f"{float(value):.1f}x" for value in display.columns]
    )

    axis.set_yticks(range(len(display.index)))
    axis.set_yticklabels(
        [f"{float(value):.1%}" for value in display.index]
    )

    axis.set_xlabel("Exit multiple")
    axis.set_ylabel("Terminal EBITDA margin")
    axis.set_title("IRR Sensitivity")

    numeric_values = display.to_numpy(dtype=float)

    for row_index in range(numeric_values.shape[0]):
        for column_index in range(numeric_values.shape[1]):
            value = float(
                numeric_values[row_index, column_index]
            )

            text = (
                "n/a"
                if not math.isfinite(value)
                else f"{value:.1f}%"
            )

            axis.text(
                column_index,
                row_index,
                text,
                ha="center",
                va="center",
            )

    fig.colorbar(
        image,
        ax=axis,
        label="IRR (%)",
    )

    fig.tight_layout()

    if out_path:
        fig.savefig(
            out_path,
            dpi=200,
            bbox_inches="tight",
        )

    return fig


def plot_monte_carlo_results(  # pragma: no cover
    mc_results: Dict[str, Any],
    out_path: Optional[str] = None,
):
    fig, axis = plt.subplots(figsize=(9, 5))
    axis.hist(mc_results["IRRs"], bins=30)
    axis.axvline(mc_results["Median_IRR"], linestyle="--", label="Median")
    axis.set_title("Unconditional Monte Carlo IRR Distribution")
    axis.set_xlabel("IRR")
    axis.set_ylabel("Scenario count")
    axis.legend()
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
    return fig


def create_enhanced_pdf_report(  # pragma: no cover
    analysis: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    if "error" in analysis:
        raise ValueError(analysis["error"])

    output_path = output_path or get_output_path("lbo_analysis.pdf")
    metrics = analysis["metrics"]
    schedule = analysis["sources_and_uses"]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "LBO Scenario Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)

    irr = metrics.get("IRR")
    irr_text = "n/a" if irr is None else f"{irr:.2%}"
    summary_lines = [
        f"IRR: {irr_text}",
        f"MOIC: {metrics.get('MOIC', math.nan):.2f}x",
        f"Initial equity: {metrics.get('Initial Equity', math.nan):,.2f}",
        f"Exit equity: {metrics.get('Equity Value', math.nan):,.2f}",
        f"Minimum ICR: {metrics.get('Min_ICR', math.nan):.2f}x",
        f"Maximum net leverage: {metrics.get('Max_Leverage', math.nan):.2f}x",
    ]
    for line in summary_lines:
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Sources and Uses", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for heading in ("sources", "uses"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, heading.title(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=10)
        for label, value in schedule[heading].items():
            pdf.cell(
                0,
                7,
                f"{label}: {value:,.2f}",
                new_x="LMARGIN",
                new_y="NEXT",
            )

    pdf.output(output_path)
    return output_path


def read_accor_assumptions(  # pragma: no cover
    csv_path: str = "data/accor_assumptions.csv",
) -> DealAssumptions:
    path = Path(csv_path)
    if not path.exists():
        return DealAssumptions()

    frame = pd.read_csv(path)
    if not {"Driver", "Base Case"}.issubset(frame.columns):
        raise ValueError("assumptions CSV must contain Driver and Base Case columns")
    values = frame.set_index("Driver")["Base Case"].astype(str)

    def percentage(name: str, default: float) -> float:
        if name not in values.index:
            return default
        return float(values.loc[name].replace("%", "").strip()) / 100.0

    def multiple(name: str, default: float) -> float:
        if name not in values.index:
            return default
        return float(values.loc[name].replace("x", "").replace("×", "").strip())

    base = DealAssumptions()
    return DealAssumptions(
        **{
            **base.__dict__,
            "entry_ev_ebitda": multiple(
                "Entry EV / EBITDA Multiple",
                base.entry_ev_ebitda,
            ),
            "exit_ev_ebitda": multiple(
                "Exit EV / EBITDA Multiple",
                base.exit_ev_ebitda,
            ),
            "rev_growth_geo": percentage(
                "Revenue CAGR (2024-29)",
                percentage(
                    "Revenue CAGR (2024–29)",
                    base.rev_growth_geo,
                ),
            ),
            "ebitda_margin_start": percentage(
                "EBITDA Margin",
                base.ebitda_margin_start,
            ),
            "tax_rate": percentage("Tax Rate", base.tax_rate),
        }
    )


if __name__ == "__main__":
    assumptions = read_accor_assumptions()
    analysis = run_comprehensive_lbo_analysis(assumptions)
    if "error" in analysis:
        raise SystemExit(analysis["error"])

    metrics = analysis["metrics"]
    print(f"IRR: {metrics['IRR']:.2%}")
    print(f"MOIC: {metrics['MOIC']:.2f}x")
    print(f"Exit equity: {metrics['Equity Value']:,.2f}")
    print(f"PDF: {create_enhanced_pdf_report(analysis)}")
