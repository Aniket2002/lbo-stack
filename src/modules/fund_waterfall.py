from typing import List, Dict, Optional
import numpy as np
import numpy_financial as npf


def irr(cashflows: List[float]) -> float:
    try:
        return npf.irr(cashflows)
    except:
        return float('nan')


def compute_waterfall_by_year(
    committed_capital: float,
    capital_calls: List[float],
    distributions: List[float],
    tiers: Optional[List[Dict[str, float]]] = None,
    gp_commitment: float = 0.02,
    mgmt_fee_pct: float = 0.02,
    reset_hurdle: bool = False,
    cashless: bool = False
) -> List[Dict[str, float]]:
    """
    Fund waterfall with fees, GP reinvestment, capital pacing, and clawback logic.

    Args:
        committed_capital: Total fund size (LP + GP)
        capital_calls: List of annual capital calls
        distributions: List of annual fund-level distributions
        tiers: List of {'hurdle': float, 'carry': float}
        gp_commitment: GP's skin-in-the-game commitment (0.02 = 2%)
        mgmt_fee_pct: Annual management fee rate (default: 2%)
        reset_hurdle: Whether to reset hurdle after each tier
        cashless: GP only accrues carry, not paid out

    Returns:
        List of dicts per year: LP/GP cash flows, fees, IRRs, etc.
    """
    if tiers is None:
        tiers = [{"hurdle": 0.08, "carry": 0.20}]

    gp_equity_pct = gp_commitment
    lp_equity_pct = 1 - gp_commitment

    waterfall = []
    lp_total, gp_total, gp_accrued = 0.0, 0.0, 0.0
    lp_cashflow = []
    gp_cashflow = []
    gross_cashflow = []

    total_drawn = 0.0

    for i, (call, dist) in enumerate(zip(capital_calls, distributions)):
        lp_call = call * lp_equity_pct
        gp_call = call * gp_equity_pct
        total_drawn += call

        mgmt_fee = committed_capital * mgmt_fee_pct
        gross_cashflow.append(-call)
        lp_cashflow.append(-lp_call - mgmt_fee)
        gp_cashflow.append(-gp_call)

        cashflows_to_date = gross_cashflow + [dist]
        gross_irr = irr(cashflows_to_date)

        applied_carry = 0.0
        for tier in tiers:
            if gross_irr > tier["hurdle"]:
                applied_carry = tier["carry"]
            else:
                break

        if reset_hurdle and applied_carry > 0:
            # Future expansion: reset base equity, not yet implemented
            pass

        gp_share = dist * applied_carry
        lp_share = dist - gp_share if not cashless else dist
        gp_paid = 0.0 if cashless else gp_share
        gp_accrued += gp_share

        lp_total += lp_share
        gp_total += gp_paid

        lp_cashflow.append(lp_share)
        gp_cashflow.append(gp_paid)
        gross_cashflow.append(dist)

        waterfall.append({
            "Year": i + 1,
            "Capital Called": call,
            "Distribution": dist,
            "Mgmt Fee": mgmt_fee,
            "GP Share": gp_paid,
            "LP Share": lp_share,
            "Cumulative LP": lp_total,
            "Cumulative GP": gp_total,
            "Accrued GP Carry (Unpaid)": gp_accrued - gp_total,
            "Gross IRR": irr(gross_cashflow),
            "Net LP IRR": irr(lp_cashflow),
            "GP IRR (Equity + Carry)": irr(gp_cashflow),
            "MOIC": (lp_total + gp_total) / total_drawn if total_drawn > 0 else 0
        })

    # Clawback check (simplified)
    final_gp_entitled = (sum(distributions) - sum(capital_calls)) * tiers[-1]["carry"]
    if gp_total > final_gp_entitled:
        clawback = gp_total - final_gp_entitled
    else:
        clawback = 0.0

    if clawback > 0:
        waterfall[-1]["GP Clawback"] = clawback
        waterfall[-1]["GP Net After Clawback"] = gp_total - clawback

    return waterfall


def summarize_waterfall(
    committed_capital: float,
    capital_calls: List[float],
    distributions: List[float],
    tiers: Optional[List[Dict[str, float]]] = None,
    gp_commitment: float = 0.02,
    mgmt_fee_pct: float = 0.02,
    reset_hurdle: bool = False,
    cashless: bool = False
) -> Dict[str, float]:
    """
    Final summary of fund-level IRRs, carry, and clawback.
    """
    results = compute_waterfall_by_year(
        committed_capital,
        capital_calls,
        distributions,
        tiers,
        gp_commitment,
        mgmt_fee_pct,
        reset_hurdle,
        cashless
    )

    final = results[-1]
    return {
        "Cumulative LP Cash": final["Cumulative LP"],
        "Cumulative GP Carry": final["Cumulative GP"],
        "Net IRR (LP)": final["Net LP IRR"],
        "Gross IRR": final["Gross IRR"],
        "GP IRR": final["GP IRR (Equity + Carry)"],
        "MOIC": final["MOIC"],
        "Clawback Triggered": final.get("GP Clawback", 0.0) > 0,
        "Clawback Amount": final.get("GP Clawback", 0.0)
    }
