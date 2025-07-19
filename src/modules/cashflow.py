from typing import List, Optional


def project_cashflows(
    revenue: float,
    rev_growth: float,
    ebitda_margin: float,
    capex_pct: float,
    debt: float,
    interest_rate: float,
    tax_rate: float,
    years: int,
    debt_amort_schedule: Optional[List[float]] = None,
    da_pct: float = 0.05,
    wc_pct: float = 0.10,  # ← NEW PARAM
) -> dict:
    """
    Projects revenue, EBITDA, D&A, CapEx, interest, taxes,
    ΔWC, and levered FCF over the forecast period.
    """

    results = {}
    debt_balance = debt
    prev_wc = revenue * wc_pct  # starting WC for year 1

    for year in range(1, years + 1):
        revenue *= 1 + rev_growth
        ebitda = revenue * ebitda_margin
        da = ebitda * da_pct
        capex = revenue * capex_pct
        interest = debt_balance * interest_rate
        amort = debt_amort_schedule[year - 1] if debt_amort_schedule else 0.0
        debt_balance = max(0, debt_balance - amort)

        curr_wc = revenue * wc_pct
        delta_wc = curr_wc - prev_wc
        prev_wc = curr_wc

        ebt = ebitda - interest - capex - da - delta_wc
        tax = max(0, ebt) * tax_rate
        lfcf = ebt - tax

        results[f"Year {year}"] = {
            "Revenue": revenue,
            "EBITDA": ebitda,
            "D&A": da,
            "CapEx": capex,
            "Interest": interest,
            "ΔWC": delta_wc,  # ← NEW FIELD
            "EBT": ebt,
            "Tax": tax,
            "Debt Amortized": amort,
            "Ending Debt": debt_balance,
            "Levered FCF": lfcf,
        }

    return results
