from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

try:
    import numpy_financial as npf
except ImportError:  # pragma: no cover
    npf = None


def _irr_fallback(cashflows: List[float]) -> float:
    if len(cashflows) < 2:
        return float("nan")
    if not any(value < 0 for value in cashflows):
        return float("nan")
    if not any(value > 0 for value in cashflows):
        return float("nan")

    rate = 0.10
    for _ in range(200):
        if rate <= -0.999999:
            rate = -0.999999

        npv = 0.0
        derivative = 0.0
        for period, cashflow in enumerate(cashflows):
            npv += cashflow / (1.0 + rate) ** period
            if period:
                derivative -= (
                    period * cashflow / (1.0 + rate) ** (period + 1)
                )

        if abs(npv) < 1e-10:
            return rate
        if abs(derivative) < 1e-12:
            break

        next_rate = rate - npv / derivative
        if not math.isfinite(next_rate):
            break
        if abs(next_rate - rate) < 1e-10:
            return next_rate
        rate = next_rate

    return float("nan")


def irr(cashflows: List[float]) -> float:
    try:
        value = (
            float(npf.irr(cashflows))
            if npf is not None
            else _irr_fallback(cashflows)
        )
    except (ValueError, TypeError, OverflowError, FloatingPointError):
        return float("nan")
    return value if math.isfinite(value) else float("nan")


def _normalise_tier(tier: Dict[str, Any]) -> Dict[str, float]:
    hurdle = float(tier.get("hurdle", tier.get("rate", 0.08)))
    carry = float(tier.get("carry", 0.20))
    if not 0 <= hurdle < 1:
        raise ValueError("hurdle must be between 0 and 1")
    if not 0 <= carry < 1:
        raise ValueError("carry must be between 0 and 1")
    return {"hurdle": hurdle, "carry": carry}


def compute_waterfall_by_year(
    committed_capital: float,
    capital_calls: List[float],
    distributions: List[float],
    tiers: Optional[List[Dict[str, Any]]] = None,
    gp_commitment: float = 0.02,
    mgmt_fee_pct: float = 0.02,
    mgmt_fee_basis: str = "committed",
    reset_hurdle: bool = False,
    cashless: bool = False,
    clawback_interest: str = "none",
) -> List[Dict[str, Any]]:
    """
    Compute a single-tier European-style whole-fund waterfall.

    Timing convention:
    - capital calls and management fees occur at the start of each annual period;
    - distributions occur at the end of each annual period;
    - the preferred return compounds annually on unreturned LP capital and
      unpaid accrued preferred return;
    - management fees are funded as separate investor outflows and are not
      deducted from gross portfolio distributions.
    """
    if committed_capital <= 0:
        raise ValueError("committed_capital must be positive")
    if not 0 <= gp_commitment < 1:
        raise ValueError("gp_commitment must be between 0 and 1")
    if not 0 <= mgmt_fee_pct < 1:
        raise ValueError("mgmt_fee_pct must be between 0 and 1")
    if mgmt_fee_basis not in {"committed", "drawn"}:
        raise ValueError("mgmt_fee_basis must be 'committed' or 'drawn'")
    if reset_hurdle:
        raise NotImplementedError("hurdle resets are not currently supported")
    if clawback_interest not in {"none", "simple"}:
        raise ValueError("clawback_interest must be 'none' or 'simple'")

    waterfall_tiers = tiers or [{"hurdle": 0.08, "carry": 0.20}]
    if len(waterfall_tiers) != 1:
        raise NotImplementedError(
            "Only a single European waterfall tier is currently supported"
        )

    tier = _normalise_tier(waterfall_tiers[0])
    hurdle = tier["hurdle"]
    carry = tier["carry"]
    lp_pct = 1.0 - gp_commitment
    gp_pct = gp_commitment

    years = max(len(capital_calls), len(distributions))
    if years == 0:
        return []

    calls = list(capital_calls) + [0.0] * (years - len(capital_calls))
    dists = list(distributions) + [0.0] * (years - len(distributions))
    if any(value < 0 for value in calls + dists):
        raise ValueError("capital calls and distributions cannot be negative")

    results: List[Dict[str, Any]] = []
    lp_cf: List[float] = []
    gp_cf: List[float] = []
    fund_cf: List[float] = []

    cumulative_calls = 0.0
    cumulative_lp_paid_in = 0.0
    cumulative_lp_distributions = 0.0
    cumulative_gp_carry_allocated = 0.0
    cumulative_gp_carry_paid = 0.0

    unreturned_lp_capital = 0.0
    unreturned_gp_capital = 0.0
    accrued_lp_pref = 0.0
    deferred_gp_carry = 0.0
    cumulative_lp_pref_paid = 0.0

    for year, (call, gross_distribution) in enumerate(
        zip(calls, dists),
        start=1,
    ):
        cumulative_calls += call
        lp_call = call * lp_pct
        gp_call = call * gp_pct
        unreturned_lp_capital += lp_call
        unreturned_gp_capital += gp_call

        fee_base = (
            committed_capital
            if mgmt_fee_basis == "committed"
            else cumulative_calls
        )
        management_fee = fee_base * mgmt_fee_pct
        lp_fee = management_fee * lp_pct
        gp_fee = management_fee * gp_pct

        cumulative_lp_paid_in += lp_call + lp_fee

        # Calls are assumed to occur at the start of the period. The LP earns
        # one annual preferred return on the current unreturned capital, while
        # any unpaid prior preferred return compounds at the same rate.
        pref_available = (
            accrued_lp_pref * (1.0 + hurdle)
            + unreturned_lp_capital * hurdle
        )

        remaining = gross_distribution
        opening_unreturned_lp = unreturned_lp_capital
        opening_unreturned_gp = unreturned_gp_capital

        # Return LP and GP contributed capital pro rata.
        total_unreturned_capital = (
            unreturned_lp_capital + unreturned_gp_capital
        )
        capital_return_pool = min(remaining, total_unreturned_capital)

        if total_unreturned_capital > 1e-12:
            lp_roc = capital_return_pool * (
                unreturned_lp_capital / total_unreturned_capital
            )
        else:
            lp_roc = 0.0
        gp_roc = capital_return_pool - lp_roc

        unreturned_lp_capital = max(
            0.0,
            unreturned_lp_capital - lp_roc,
        )
        unreturned_gp_capital = max(
            0.0,
            unreturned_gp_capital - gp_roc,
        )
        remaining -= capital_return_pool

        # Pay the compounded LP preferred return.
        pref_paid = min(remaining, pref_available)
        accrued_lp_pref = pref_available - pref_paid
        cumulative_lp_pref_paid += pref_paid
        remaining -= pref_paid

        # A 100% GP catch-up brings cumulative GP carry to the contractual
        # share of the LP preferred return before the residual split begins.
        catch_up_target = (
            cumulative_lp_pref_paid * carry / max(1e-12, 1.0 - carry)
        )
        catch_up_needed = max(
            0.0,
            catch_up_target - cumulative_gp_carry_allocated,
        )
        catch_up = min(remaining, catch_up_needed)
        remaining -= catch_up

        residual_gp = remaining * carry
        residual_lp = remaining - residual_gp
        remaining = 0.0

        gp_carry_allocated = catch_up + residual_gp
        cumulative_gp_carry_allocated += gp_carry_allocated

        lp_distribution = lp_roc + pref_paid + residual_lp
        gp_economic_distribution = gp_roc + gp_carry_allocated

        gp_carry_paid_this_year = 0.0
        gp_final_pay = 0.0
        if cashless:
            deferred_gp_carry += gp_carry_allocated
            if year == years:
                gp_final_pay = deferred_gp_carry
                gp_carry_paid_this_year = gp_final_pay
                deferred_gp_carry = 0.0
        else:
            gp_carry_paid_this_year = gp_carry_allocated

        gp_cash_distribution = gp_roc + gp_carry_paid_this_year
        cumulative_gp_carry_paid += gp_carry_paid_this_year
        cumulative_lp_distributions += lp_distribution

        lp_period_cf = -lp_call - lp_fee + lp_distribution
        gp_period_cf = -gp_call - gp_fee + gp_cash_distribution
        fund_period_cf = -call - management_fee + gross_distribution

        lp_cf.append(lp_period_cf)
        gp_cf.append(gp_period_cf)
        fund_cf.append(fund_period_cf)

        distribution_delta = (
            gross_distribution
            - lp_distribution
            - gp_economic_distribution
        )
        if abs(distribution_delta) > 1e-8:
            raise AssertionError(
                f"Year {year}: gross distribution failed to reconcile by "
                f"{distribution_delta:.10f}"
            )

        results.append(
            {
                "Year": year,
                "Capital Called": call,
                "LP Called": lp_call,
                "GP Called": gp_call,
                "Mgmt Fee": management_fee,
                "LP Fee": lp_fee,
                "GP Fee": gp_fee,
                "Gross Dist": gross_distribution,
                "Net Dist": gross_distribution,
                "Opening Unreturned LP Capital": opening_unreturned_lp,
                "Opening Unreturned GP Capital": opening_unreturned_gp,
                "LP Return of Capital": lp_roc,
                "GP Return of Capital": gp_roc,
                "Return of Capital": capital_return_pool,
                "Preferred Return Accrued": pref_available,
                "Preferred Return Paid": pref_paid,
                "Closing Accrued Preferred Return": accrued_lp_pref,
                "Catch-up Paid": catch_up,
                "Residual LP": residual_lp,
                "Residual GP": residual_gp,
                "GP Carry Allocated": gp_carry_allocated,
                "GP Carry Paid": gp_carry_paid_this_year,
                "GP Carry Deferred": deferred_gp_carry,
                "LP Distributed": lp_distribution,
                "GP Distributed": gp_cash_distribution,
                "GP Economic Distribution": gp_economic_distribution,
                "GP Final Pay": gp_final_pay,
                "LP Cash Flow": lp_period_cf,
                "GP Cash Flow": gp_period_cf,
                "Fund Cash Flow": fund_period_cf,
                "Gross Distribution Reconciliation": (
                    lp_distribution + gp_economic_distribution
                ),
                "Gross Distribution Delta": distribution_delta,
                "LP + GP Reconciliation": (
                    lp_distribution + gp_economic_distribution
                ),
                "LP Distributions + GP Distributions": (
                    lp_distribution + gp_economic_distribution
                ),
                "Closing Unreturned LP Capital": unreturned_lp_capital,
                "Closing Unreturned GP Capital": unreturned_gp_capital,
                "Tier Detail": [
                    {
                        "Tier": 1,
                        "Hurdle": hurdle,
                        "Carry": carry,
                        "LP ROC": lp_roc,
                        "GP ROC": gp_roc,
                        "Preferred Return": pref_paid,
                        "Catch-up": catch_up,
                        "Residual LP": residual_lp,
                        "Residual GP": residual_gp,
                    }
                ],
                "Cumulative LP Paid In": cumulative_lp_paid_in,
                "Cumulative LP Distributed": cumulative_lp_distributions,
            }
        )

    total_profit = max(0.0, sum(dists) - sum(calls))
    final_carry_entitlement = total_profit * carry
    excess_carry = max(
        0.0,
        cumulative_gp_carry_paid - final_carry_entitlement,
    )

    clawback = 0.0
    if excess_carry > 1e-8:
        clawback = excess_carry
        if clawback_interest == "simple":
            clawback *= 1.0 + hurdle * years
        gp_cf[-1] -= clawback
        lp_cf[-1] += clawback
        results[-1]["Clawback"] = clawback
        results[-1]["GP Net After Clawback"] = (
            cumulative_gp_carry_paid - clawback
        )

    for index, row in enumerate(results, start=1):
        row["LP IRR"] = irr(lp_cf[:index])
        row["GP IRR"] = irr(gp_cf[:index])
        row["Fund IRR"] = irr(fund_cf[:index])
        paid_in = row["Cumulative LP Paid In"]
        row["MOIC"] = (
            row["Cumulative LP Distributed"] / paid_in
            if paid_in > 0
            else 0.0
        )

    return results


def summarize_waterfall(
    committed_capital: float,
    capital_calls: List[float],
    distributions: List[float],
    tiers: Optional[List[Dict[str, Any]]] = None,
    gp_commitment: float = 0.02,
    mgmt_fee_pct: float = 0.02,
    mgmt_fee_basis: str = "committed",
    reset_hurdle: bool = False,
    cashless: bool = False,
    clawback_interest: str = "none",
) -> Dict[str, Any]:
    waterfall = compute_waterfall_by_year(
        committed_capital=committed_capital,
        capital_calls=capital_calls,
        distributions=distributions,
        tiers=tiers,
        gp_commitment=gp_commitment,
        mgmt_fee_pct=mgmt_fee_pct,
        mgmt_fee_basis=mgmt_fee_basis,
        reset_hurdle=reset_hurdle,
        cashless=cashless,
        clawback_interest=clawback_interest,
    )
    if not waterfall:
        return {}

    last = waterfall[-1]
    return {
        "Cumulative LP Distributed": sum(
            row["LP Distributed"] for row in waterfall
        ),
        "Cumulative GP Cash Distributed": sum(
            row["GP Distributed"] for row in waterfall
        ),
        "Cumulative GP Carry Allocated": sum(
            row["GP Carry Allocated"] for row in waterfall
        ),
        "Cumulative Mgmt Fee": sum(row["Mgmt Fee"] for row in waterfall),
        "Net IRR (LP)": last["LP IRR"],
        "Net IRR (GP)": last["GP IRR"],
        "Fund IRR": last["Fund IRR"],
        "MOIC": last["MOIC"],
        "Clawback Triggered": "Clawback" in last,
        "Clawback Amount": last.get("Clawback", 0.0),
    }
