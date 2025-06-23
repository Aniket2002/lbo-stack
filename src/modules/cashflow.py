def project_cashflows(
    revenue: float,
    rev_growth: float,
    ebitda_margin: float,
    capex_pct: float,
    debt: float,
    interest_rate: float,
    years: int
) -> dict:
    """
    Projects revenue, EBITDA, CapEx, interest, and FCF over the forecast period.

    Returns:
        Dict[year, metrics]
    """
    results = {}

    for year in range(1, years + 1):
        revenue *= (1 + rev_growth)
        ebitda = revenue * ebitda_margin
        capex = revenue * capex_pct
        interest = debt * interest_rate
        fcf = ebitda - capex - interest

        results[f"Year {year}"] = {
            "Revenue": revenue,
            "EBITDA": ebitda,
            "CapEx": capex,
            "Interest": interest,
            "FCF": fcf
        }

    return results
