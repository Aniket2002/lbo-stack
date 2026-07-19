# src/modules/fund_waterfall.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import numpy_financial as npf
except Exception:  # pragma: no cover - local fallback when optional dependency is missing
    npf = None


def _irr_fallback(cashflows: List[float]) -> float:
    if len(cashflows) < 2:
        return float("nan")

    rate = 0.1
    for _ in range(100):
        npv = 0.0
        d_npv = 0.0
        for period, cashflow in enumerate(cashflows):
            discount = (1 + rate) ** period
            npv += cashflow / discount
            if period > 0:
                d_npv -= period * cashflow / ((1 + rate) ** (period + 1))
        if abs(d_npv) < 1e-12:
            break
        next_rate = rate - npv / d_npv
        if abs(next_rate - rate) < 1e-10:
            rate = next_rate
            break
        rate = next_rate
    return rate


def irr(cashflows: List[float]) -> float:
    """Compute IRR with a fallback when numpy_financial is unavailable."""
    try:
        if npf is not None:
            return float(npf.irr(cashflows))
        return _irr_fallback(cashflows)
    except Exception:
        return float("nan")


def _tier_rate(tier: Dict[str, Any]) -> float:
    return float(tier.get("hurdle", tier.get("rate", 0.08)))


def _tier_carry(tier: Dict[str, Any]) -> float:
    return float(tier.get("carry", 0.20))


def _normalise_tiers(tiers: Optional[List[Dict[str, Any]]]) -> List[Dict[str, float]]:
    normalised = tiers or [{"hurdle": 0.08, "carry": 0.20}]
    return sorted(
        [{"hurdle": _tier_rate(t), "carry": _tier_carry(t)} for t in normalised],
        key=lambda tier: tier["hurdle"],
    )


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
    clawback_interest: str = "simple",
) -> List[Dict[str, float]]:
    """
    Compute a fund waterfall from first principles.

    Outputs include annual fund, LP, and GP cash-flow vectors plus the usual
    waterfall breakdown: return of capital, preferred return, catch-up,
    residual split, cashless carry accrual, and clawback.
    """
    waterfall_tiers = _normalise_tiers(tiers)
    gp_pct = float(gp_commitment)
    lp_pct = 1.0 - gp_pct

    years = max(len(capital_calls), len(distributions))
    calls = list(capital_calls) + [0.0] * max(0, years - len(capital_calls))
    dists = list(distributions) + [0.0] * max(0, years - len(distributions))

    results: List[Dict[str, float]] = []
    fund_cf: List[float] = []
    lp_cf: List[float] = []
    gp_cf: List[float] = []

    cumulative_calls = 0.0
    cumulative_fees = 0.0
    cumulative_net_distributions = 0.0
    lp_contributed = 0.0
    lp_returned_capital = 0.0
    lp_pref_accrued = 0.0
    lp_pref_paid = 0.0
    gp_carry_paid = 0.0
    gp_carry_accrued = 0.0

    for year, (call, gross_dist) in enumerate(zip(calls, dists), start=1):
        cumulative_calls += call
        lp_call = call * lp_pct
        gp_call = call * gp_pct
        lp_contributed += lp_call

        fee_base = committed_capital if mgmt_fee_basis == "committed" else cumulative_calls
        mgmt_fee = fee_base * mgmt_fee_pct
        fee_lp = mgmt_fee * lp_pct
        fee_gp = mgmt_fee * gp_pct
        cumulative_fees += mgmt_fee

        net_dist = max(0.0, gross_dist - mgmt_fee)
        cumulative_net_distributions += net_dist

        opening_unreturned_capital = max(0.0, lp_contributed - lp_returned_capital)
        remaining = net_dist
        lp_distribution = 0.0
        gp_distribution = 0.0
        tier_rows: List[Dict[str, float]] = []

        for tier_index, tier in enumerate(waterfall_tiers):
            if remaining <= 0:
                tier_rows.append(
                    {
                        "Tier": float(tier_index + 1),
                        "Hurdle": tier["hurdle"],
                        "Carry": tier["carry"],
                        "ROC": 0.0,
                        "Preferred Return": 0.0,
                        "Catch-up": 0.0,
                        "Residual LP": 0.0,
                        "Residual GP": 0.0,
                    }
                )
                continue

            hurdle = tier["hurdle"]
            carry = tier["carry"]

            # Return of capital for the LP first.
            roc = min(remaining, opening_unreturned_capital)
            lp_distribution += roc
            lp_returned_capital += roc
            remaining -= roc

            # Preferred return accrues on unreturned LP capital.
            pref_due = opening_unreturned_capital * hurdle
            if reset_hurdle and tier_index > 0:
                pref_due = 0.0
            pref_pay = min(remaining, max(0.0, pref_due - lp_pref_paid))
            lp_distribution += pref_pay
            lp_pref_paid += pref_pay
            lp_pref_accrued += max(0.0, pref_due - pref_pay)
            remaining -= pref_pay

            # Catch-up: GP receives 100% until its paid carry matches the target
            # share of excess profits above capital and paid pref.
            excess_profit = max(
                0.0,
                cumulative_net_distributions - lp_contributed - lp_pref_paid,
            )
            gp_target = excess_profit * carry / max(1e-9, 1.0 - carry)
            catch_up = min(remaining, max(0.0, gp_target - gp_carry_paid))
            gp_distribution += catch_up
            gp_carry_paid += catch_up
            remaining -= catch_up

            # Residual split according to the tier carry.
            residual_gp = remaining * carry
            residual_lp = remaining - residual_gp
            gp_distribution += residual_gp
            lp_distribution += residual_lp
            gp_carry_paid += residual_gp
            remaining = 0.0

            tier_rows.append(
                {
                    "Tier": float(tier_index + 1),
                    "Hurdle": hurdle,
                    "Carry": carry,
                    "ROC": roc,
                    "Preferred Return": pref_pay,
                    "Catch-up": catch_up,
                    "Residual LP": residual_lp,
                    "Residual GP": residual_gp,
                }
            )

        while len(tier_rows) < len(waterfall_tiers):
            tier_index = len(tier_rows)
            tier = waterfall_tiers[tier_index]
            tier_rows.append(
                {
                    "Tier": float(tier_index + 1),
                    "Hurdle": tier["hurdle"],
                    "Carry": tier["carry"],
                    "ROC": 0.0,
                    "Preferred Return": 0.0,
                    "Catch-up": 0.0,
                    "Residual LP": 0.0,
                    "Residual GP": 0.0,
                }
            )

        # Cashless carry accrues but is not paid until the final year.
        carried_this_year = gp_distribution
        if cashless:
            gp_carry_accrued += carried_this_year
            gp_paid = 0.0
        else:
            gp_carry_accrued += carried_this_year
            gp_paid = carried_this_year

        lp_cf.append(-lp_call - fee_lp + lp_distribution)
        gp_cf.append(-gp_call - fee_gp + gp_paid)
        fund_cf.append(gross_dist - call - mgmt_fee)

        lp_vector = lp_distribution - fee_lp
        gp_vector = gp_paid - fee_gp

        results.append(
            {
                "Year": float(year),
                "Capital Called": call,
                "Gross Dist": gross_dist,
                "Mgmt Fee": mgmt_fee,
                "Net Dist": net_dist,
                "LP Called": lp_call,
                "GP Called": gp_call,
                "LP Distributed": lp_distribution,
                "GP Distributed": gp_paid,
                "LP Cash Flow": lp_cf[-1],
                "GP Cash Flow": gp_cf[-1],
                "Fund Cash Flow": fund_cf[-1],
                "LP Vector": lp_vector,
                "GP Vector": gp_vector,
                "Fund Vector": fund_cf[-1],
                "Return of Capital": lp_distribution - max(0.0, lp_distribution - lp_pref_paid),
                "Preferred Return Paid": lp_pref_paid,
                "Catch-up Paid": carried_this_year if cashless else gp_distribution,
                "Carry Paid": gp_paid,
                "Gross Distribution Reconciliation": lp_distribution + gp_paid + mgmt_fee,
                "Net Distribution Reconciliation": lp_distribution + gp_paid,
                "LP + GP Reconciliation": lp_distribution + gp_paid,
                "LP Distributions + GP Distributions": lp_distribution + gp_paid,
                "Tier Detail": tier_rows,
                "GP Carry Accrued": gp_carry_accrued,
            }
        )

    # Final cashless carry payout and clawback reconciliation.
    if cashless and gp_carry_accrued > 0:
        results[-1]["GP Final Pay"] = gp_carry_accrued
        gp_cf[-1] += gp_carry_accrued
        gp_carry_paid += gp_carry_accrued
        results[-1]["GP Distributed"] += gp_carry_accrued
        results[-1]["Gross Distribution Reconciliation"] += gp_carry_accrued

    total_call = sum(calls)
    total_dist = sum(dists)
    total_profit = max(0.0, total_dist - total_call - cumulative_fees)
    target_gp = total_profit * waterfall_tiers[-1]["carry"]
    excess_gp = max(0.0, gp_carry_paid - target_gp)

    if excess_gp > 0:
        rate = waterfall_tiers[-1]["hurdle"]
        clawback = excess_gp * (1.0 + rate * years) if clawback_interest == "simple" else excess_gp
        results[-1]["Clawback"] = clawback
        results[-1]["GP Net After Clawback"] = gp_carry_paid - clawback
        gp_cf[-1] -= clawback
        lp_cf[-1] += clawback
        results[-1]["Gross Distribution Reconciliation"] += 0.0
        results[-1]["LP + GP Reconciliation"] += 0.0

    for row in results:
        row["Gross Distribution Reconciliation"] = row["LP Distributed"] + row["GP Distributed"] + row["Mgmt Fee"]
        row["LP + GP Reconciliation"] = row["LP Distributed"] + row["GP Distributed"]
        row["LP Distributions + GP Distributions"] = row["LP Distributed"] + row["GP Distributed"]
        row["LP IRR"] = irr(lp_cf[: int(row["Year"])])
        row["GP IRR"] = irr(gp_cf[: int(row["Year"])])
        row["Fund IRR"] = irr(fund_cf[: int(row["Year"])])
        row["MOIC"] = (
            sum(x["LP Distributed"] for x in results[: int(row["Year"])]) / lp_contributed
            if lp_contributed
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
    clawback_interest: str = "simple",
) -> Dict[str, float]:
    """Return a compact fund-level summary from the yearly waterfall."""
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
    last = waterfall[-1]
    return {
        "Cumulative LP Distributed": sum(row["LP Distributed"] for row in waterfall),
        "Cumulative GP Distributed": sum(row["GP Distributed"] for row in waterfall),
        "Cumulative Mgmt Fee": sum(row["Mgmt Fee"] for row in waterfall),
        "Net IRR (LP)": last["LP IRR"],
        "Net IRR (GP)": last["GP IRR"],
        "Fund IRR": last["Fund IRR"],
        "MOIC": last["MOIC"],
        "Clawback Triggered": "Clawback" in last,
        "Clawback Amount": last.get("Clawback", 0.0),
    }