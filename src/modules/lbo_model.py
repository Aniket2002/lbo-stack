from modules.cashflow import project_cashflows
from modules.exit import calculate_exit

class LBOModel:
    def __init__(
        self,
        enterprise_value: float,
        debt_pct: float,
        revenue: float,
        rev_growth: float,
        ebitda_margin: float,
        capex_pct: float,
        exit_multiple: float,
        interest_rate: float
    ):
        self.ev = enterprise_value
        self.debt_pct = debt_pct
        self.revenue = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.capex_pct = capex_pct
        self.exit_multiple = exit_multiple
        self.interest_rate = interest_rate

        self.equity = enterprise_value * (1 - debt_pct)
        self.debt = enterprise_value * debt_pct

    def run(self, years: int = 5) -> dict:
        results = project_cashflows(
            revenue=self.revenue,
            rev_growth=self.rev_growth,
            ebitda_margin=self.ebitda_margin,
            capex_pct=self.capex_pct,
            debt=self.debt,
            interest_rate=self.interest_rate,
            years=years
        )

        last_ebitda = results[f"Year {years}"]["EBITDA"]
        exit_summary = calculate_exit(
            final_year_ebitda=last_ebitda,
            exit_multiple=self.exit_multiple,
            debt=self.debt,
            initial_equity=self.equity,
            years=years
        )

        results["Exit Summary"] = exit_summary
        return results
