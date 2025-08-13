
# src/modules/fund_waterfall.py

from typing import Any, Dict, List, Optional

import numpy_financial as npf


def irr(cashflows: List[float]) -> float:
    """
    Compute the IRR of a list of cashflows, returning NaN if it fails.
    """
    try:
        return npf.irr(cashflows)
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

    gp_pct, lp_pct = gp_commitment, 1 - gp_commitment

    results: List[Dict[str, float]] = []
    pre_fee_cf: List[float] = []
    netfee_cf: List[float] = []  # for Net-Fees IRR
    lp_cf: List[float] = []
    gp_cf: List[float] = []

    total_drawn = 0.0
    lp_called = gp_called = 0.0
    lp_distributed = gp_paid = gp_accrued = gp_entitlement = 0.0

    for year, (call, dist) in enumerate(zip(capital_calls, distributions), start=1):
        # 1) Capital call
        total_drawn += call
        lp_part, gp_part = call * lp_pct, call * gp_pct
        lp_called += lp_part
        gp_called += gp_part

        # 2) Management fee
        fee_base = committed_capital if mgmt_fee_basis == "committed" else total_drawn
        fee = fee_base * mgmt_fee_pct

        # 3) Record call CFs
        pre_fee_cf.append(-call)
        netfee_cf.append(-call)
        lp_cf.append(-lp_part - fee)
        gp_cf.append(-gp_part)

        # 4) Net distribution
        net_dist = max(0.0, dist - fee)

        # 5) Paid-in capital gate
        remaining = net_dist
        lp_share = gp_share = 0.0
        if lp_distributed < lp_called:
            makeup = min(remaining, lp_called - lp_distributed)
            lp_share += makeup
            remaining -= makeup

        # 6) Pre-Fee IRR
        pre_fee_cf.append(dist)
        pre_fee_irr = irr(pre_fee_cf)

        # 7) Initialize gross IRR (will not be used for Net-Fees)
        #    actual Net-Fees IRR computed after CF appends below

        # 8) Carry allocation with true catch-up
        for tier in local_tiers:
            cp, hr = tier["carry"], tier["rate"]
            ttype = tier["type"]

            # hurdle check
            if ttype == "simple":
                if (sum(distributions[:year]) / total_drawn) < hr:
                    break
            else:
                # use last computed netfees_irr if exists, else assume enough
                pass

            # net profit base = Σdist – Σcalls
            total_dist = lp_distributed + lp_share + gp_paid + gp_accrued + remaining
            profit = max(0.0, total_dist - (lp_called + gp_called))
            target = profit * cp
            need = max(0.0, target - (gp_accrued + gp_paid))
            alloc = min(remaining, need)

            gp_share += alloc
            remaining -= alloc
            gp_accrued += alloc
            gp_entitlement += alloc

            if reset_hurdle:
                netfee_cf = []

        # 9) Residual to LP
        lp_share += remaining
        remaining = 0.0
        lp_distributed += lp_share

        # 10) Record distribution CFs
        netfee_cf.append(lp_share + gp_share)
        lp_cf.append(lp_share)
        if cashless:
            gp_cf.append(-gp_share)
        else:
            gp_cf.append(gp_share)
            gp_paid += gp_share

        # 11) Net-Fees IRR recompute after full CFs
        netfees_irr = irr(netfee_cf)

        # 12) Yearly summary
        results.append(
            {
                "Year": year,
                "Capital Called": call,
                "Mgmt Fee": fee,
                "Gross Dist": dist,
                "Net Dist": net_dist,
                "LP Called": lp_part,
                "GP Called": gp_part,
                "LP Distributed": lp_share,
                "GP Paid": 0.0 if cashless else gp_share,
                "GP Accrued": gp_accrued,
                "Pre-Fee IRR": pre_fee_irr,
                "Net-Fees IRR": netfees_irr,
                "LP IRR": irr(lp_cf),
                "GP IRR": irr(gp_cf),
                "MOIC": (lp_distributed / lp_called) if lp_called else 0.0,
            }
        )

    # 13) Final cashless payout
    if cashless and gp_accrued > 0:
        gp_cf.append(gp_accrued)
        results[-1]["GP Final Pay"] = gp_accrued
        gp_paid += gp_accrued
        # recompute final metrics
        results[-1].update(
            {
                "GP IRR": irr(gp_cf),
                "Net-Fees IRR": irr(netfee_cf),
                "LP IRR": irr(lp_cf),
                "MOIC": (lp_distributed / lp_called) if lp_called else 0.0,
            }
        )

    # 14) Clawback processing
    total_dist = sum(distributions)
    profit_final = total_dist - total_drawn
    final_ent = profit_final * local_tiers[-1]["carry"]
    excess = (
        gp_paid - gp_entitlement
        if gp_entitlement > 0
        else max(0.0, gp_paid - final_ent)
    )
    if excess > 0:
        rate = local_tiers[-1]["rate"]
        claw = (
            excess * (1 + rate * len(results))
            if clawback_interest == "simple"
            else excess
        )
        results[-1]["Clawback"] = claw
        results[-1]["GP Net After Clawback"] = gp_paid - claw
        gp_cf.append(-claw)
        lp_cf.append(claw)
        netfee_cf.append(0.0)
        # recompute after clawback
        results[-1].update(
            {
                "GP IRR": irr(gp_cf),
                "Net-Fees IRR": irr(netfee_cf),
                "LP IRR": irr(lp_cf),
                "MOIC": (lp_distributed / lp_called) if lp_called else 0.0,
            }
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
