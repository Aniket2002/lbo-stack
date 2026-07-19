
# src/modules/fund_waterfall.py

from typing import Any, Dict, List, Optional

try:
    import numpy_financial as npf
except Exception:  # pragma: no cover - fallback for local environments without the package
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
    """
    Compute the IRR of a list of cashflows, returning NaN if it fails.
    """
    try:
        if npf is not None:
            return float(npf.irr(cashflows))
        return _irr_fallback(cashflows)
    except Exception:
        return float("nan")


def compute_waterfall_by_year(
    committed_capital: float,
    capital_calls: List[float],
    distributions: List[float],
    tiers: Optional[List[Dict[str, Any]]] = None,
    gp_commitment: float = 0.02,
    mgmt_fee_pct: float = 0.02,
    mgmt_fee_basis: str = "committed",  # "committed" or "drawn"
    reset_hurdle: bool = False,
    cashless: bool = False,
    clawback_interest: str = "simple",  # "simple" or "none"
) -> List[Dict[str, float]]:
    """
    Compute a full fund waterfall, USD millions.

    Key features:
      - Paid-in capital return gate
      - True 100% catch-up per hurdle tier
      - Carry on net profit (Σdist – Σcalls)
      - Management fees on committed vs drawn capital
      - Optional hurdle reset
      - Cashless deferral + final GP payout
      - Clawback with simple interest at hurdle × years (no compounding)
      - GP CF outflows and LP credit for clawback so IRRs include them

    IRR labels:
      - Pre-Fee IRR = pre-fee IRR on gross distributions
      - Net-Fees IRR = post-fee, pre-carry IRR

    Args:
        committed_capital: total fund size
        capital_calls: annual calls
        distributions: annual distributions
        tiers: each {"type":"irr"/"simple", "rate":hurdle, "carry":pct}
        gp_commitment: GP % of calls
        mgmt_fee_pct: annual fee %
        mgmt_fee_basis: "committed" or "drawn"
        reset_hurdle: reset IRR base after each tier
        cashless: defer GP carry until final year
        clawback_interest: "simple" or "none"

    Returns:
        List of per-year waterfall dicts with keys:
          Year, Capital Called, Mgmt Fee,
          Gross Dist, Net Dist,
          LP Called, GP Called,
          LP Distributed, GP Paid, GP Accrued,
          Pre-Fee IRR, Net-Fees IRR, LP IRR, GP IRR, MOIC,
          + GP Final Pay, Clawback, GP Net After Clawback on last year.
    """
    default_tier = {"type": "irr", "rate": 0.08, "carry": 0.20}
    local_tiers = sorted((tiers or [default_tier]), key=lambda t: t["rate"])
    first_tier = local_tiers[0]
    target_carry = first_tier["carry"]

    gp_pct, lp_pct = gp_commitment, 1 - gp_commitment

    results: List[Dict[str, float]] = []
    lp_cf: List[float] = []
    gp_cf: List[float] = []
    gross_cf: List[float] = []

    total_drawn = 0.0
    lp_called = 0.0
    gp_called = 0.0
    lp_capital_recovered = 0.0
    gp_accrued = 0.0
    gp_paid = 0.0
    carried_interest_paid = 0.0
    pref_accrued = 0.0
    carry_basis_profit = 0.0

    for year, (call, dist) in enumerate(zip(capital_calls, distributions), start=1):
        total_drawn += call
        lp_call = call * lp_pct
        gp_call = call * gp_pct
        lp_called += lp_call
        gp_called += gp_call

        fee_base = committed_capital if mgmt_fee_basis == "committed" else total_drawn
        fee = fee_base * mgmt_fee_pct
        distributable = max(0.0, dist - fee)

        pre_fee_cf = list(gross_cf)
        pre_fee_cf.append(dist)
        pre_fee_irr = irr(pre_fee_cf)

        gross_cf.append(dist)
        lp_cf.append(-lp_call - fee)
        gp_cf.append(-gp_call)

        opening_pref = pref_accrued
        pref_accrued = opening_pref * (1 + first_tier["rate"])
        carry_basis_profit += max(0.0, distributable - call)

        remaining = distributable
        lp_share = 0.0
        gp_share = 0.0
        roc_paid = 0.0
        pref_paid = 0.0
        catch_up_paid = 0.0
        carry_paid = 0.0

        roc_need = max(0.0, lp_called - lp_capital_recovered)
        roc_alloc = min(remaining, roc_need)
        lp_share += roc_alloc
        roc_paid = roc_alloc
        lp_capital_recovered += roc_alloc
        remaining -= roc_alloc

        pref_need = max(0.0, pref_accrued)
        pref_alloc = min(remaining, pref_need)
        lp_share += pref_alloc
        pref_paid = pref_alloc
        pref_accrued = max(0.0, pref_accrued - pref_alloc)
        remaining -= pref_alloc

        if remaining > 0 and target_carry > 0:
            carry_target = carry_basis_profit * target_carry
            catch_up_need = max(0.0, carry_target - gp_accrued)
            catch_up_alloc = min(remaining, catch_up_need)
            gp_share += catch_up_alloc
            catch_up_paid = catch_up_alloc
            gp_accrued += catch_up_alloc
            remaining -= catch_up_alloc

        if remaining > 0:
            carry_alloc = remaining * target_carry
            lp_residual = remaining - carry_alloc
            gp_share += carry_alloc
            lp_share += lp_residual
            carry_paid = carry_alloc
            gp_accrued += carry_alloc
            remaining = 0.0

        lp_cf.append(lp_share)
        if cashless:
            gp_cf.append(0.0)
            gp_accrued += gp_share
            carried_interest_paid += gp_share
        else:
            gp_cf.append(gp_share)
            gp_paid += gp_share
            carried_interest_paid += gp_share

        netfee_cf = lp_cf + gp_cf
        results.append(
            {
                "Year": year,
                "Capital Called": call,
                "Mgmt Fee": fee,
                "Gross Dist": dist,
                "Net Dist": distributable,
                "LP Called": lp_call,
                "GP Called": gp_call,
                "LP Distributed": lp_share,
                "GP Distributed": gp_share,
                "GP Paid": gp_share if not cashless else 0.0,
                "GP Accrued": gp_accrued,
                "ROC Paid": roc_paid,
                "Preferred Return Paid": pref_paid,
                "Catch-up Paid": catch_up_paid,
                "Carry Paid": carry_paid,
                "Pre-Fee IRR": pre_fee_irr,
                "Net-Fees IRR": irr(netfee_cf),
                "LP IRR": irr(lp_cf),
                "GP IRR": irr(gp_cf),
                "MOIC": (sum(r["LP Distributed"] for r in results) / lp_called) if lp_called else 0.0,
                "Gross Reconciliation": dist,
                "LP + GP Reconciliation": lp_share + gp_share,
            }
        )

        if reset_hurdle:
            pref_accrued = 0.0

    if cashless and gp_accrued > 0:
        gp_cf.append(gp_accrued)
        results[-1]["GP Final Pay"] = gp_accrued
        gp_paid += gp_accrued
        carried_interest_paid += gp_accrued
        results[-1].update(
            {
                "GP IRR": irr(gp_cf),
                "Net-Fees IRR": irr(lp_cf + gp_cf),
                "LP IRR": irr(lp_cf),
            }
        )

    total_dist = sum(distributions)
    total_call = sum(capital_calls)
    gp_entitlement = max(0.0, (total_dist - total_call) * target_carry)
    excess = max(0.0, gp_paid - gp_entitlement)
    if excess > 0:
        rate = first_tier["rate"]
        claw = excess * (1 + rate * len(results)) if clawback_interest == "simple" else excess
        results[-1]["Clawback"] = claw
        results[-1]["GP Net After Clawback"] = gp_paid - claw
        gp_cf.append(-claw)
        lp_cf.append(claw)
        results[-1].update(
            {
                "GP IRR": irr(gp_cf),
                "Net-Fees IRR": irr(lp_cf + gp_cf),
                "LP IRR": irr(lp_cf),
            }
        )

    for row in results:
        row["LP Distributions + GP Distributions"] = row["LP Distributed"] + row["GP Distributed"]

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
    """
    Final summary of fund-level metrics.
    """
    wf = compute_waterfall_by_year(
        committed_capital,
        capital_calls,
        distributions,
        tiers,
        gp_commitment,
        mgmt_fee_pct,
        mgmt_fee_basis,
        reset_hurdle,
        cashless,
        clawback_interest,
    )
    last = wf[-1]
    cumulative_lp = sum(r["LP Distributed"] for r in wf)
    cumulative_gp = sum(r.get("GP Paid", 0.0) for r in wf) + last.get(
        "GP Final Pay", 0.0
    )
    return {
        "Cumulative LP Distributed": cumulative_lp,
        "Cumulative GP Paid": cumulative_gp,
        "Net IRR (LP)": last["LP IRR"],
        "Pre-Fee IRR": last["Pre-Fee IRR"],
        "Net-Fees IRR": last["Net-Fees IRR"],
        "GP IRR": last["GP IRR"],
        "MOIC": last["MOIC"],
        "Clawback Triggered": "Clawback" in last,
        "Clawback Amount": last.get("Clawback", 0.0),
    }
