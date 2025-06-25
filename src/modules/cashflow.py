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
) -> dict:
    """
    Projects revenue, EBITDA, CapEx, interest, taxes,
    and levered FCF over the forecast period.
    """

    results = {}
    debt_balance = debt

    for year in range(1, years + 1):
        revenue *= 1 + rev_growth
        ebitda = revenue * ebitda_margin
        capex = revenue * capex_pct
        interest = debt_balance * interest_rate
        amort = debt_amort_schedule[year - 1] if debt_amort_schedule else 0.0
        debt_balance = max(0, debt_balance - amort)

        ebt = ebitda - interest - capex
        tax = max(0, ebt) * tax_rate
        lfcf = ebt - tax

        results[f"Year {year}"] = {
            "Revenue": revenue,
            "EBITDA": ebitda,
            "CapEx": capex,
            "Interest": interest,
            "EBT": ebt,
            "Tax": tax,
            "Debt Amortized": amort,
            "Ending Debt": debt_balance,
            "Levered FCF": lfcf,
        }

    return results
