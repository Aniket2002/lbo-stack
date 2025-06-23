from typing import Dict, Any
import numpy as np
import numpy_financial as npf

class LBOModel:
    def __init__(
        self,
        enterprise_value: float,
        debt_pct: float,
        revenue: float,
        rev_growth: float,
        ebitda_margin: float,
        capex_pct: float,
        wc_pct: float,
        tax_rate: float,
        exit_multiple: float,
        interest_rate: float
    ):
        # ✅ Input validation
        assert 0 <= debt_pct <= 1, "Debt % must be between 0 and 1"
        assert 0 <= capex_pct <= 1, "CapEx % must be between 0 and 1"
        assert -1 < rev_growth < 2, "Unrealistic revenue growth"
        assert 0 <= ebitda_margin <= 1, "EBITDA margin must be between 0 and 1"
        assert 0 <= tax_rate <= 1, "Tax rate must be between 0 and 1"
        assert 0 <= wc_pct <= 1, "Working capital % must be between 0 and 1"
        assert exit_multiple > 0, "Exit multiple must be positive"
        assert interest_rate >= 0, "Interest rate must be non-negative"

        self.ev = enterprise_value
        self.debt_pct = debt_pct
        self.revenue = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.capex_pct = capex_pct
        self.wc_pct = wc_pct
        self.tax_rate = tax_rate
        self.exit_multiple = exit_multiple
        self.interest_rate = interest_rate

        self.debt = self.ev * self.debt_pct
        self.equity = self.ev - self.debt

    def run(self, years: int = 5, use_sweep: bool = False) -> Dict[str, Any]:
        results = {}
        revenue = self.revenue
        wc_balance = revenue * self.wc_pct
        fcf_list = []

        debt_balance = self.debt
        cash_balance = 0
        annual_amort = self.debt / years

        for year in range(1, years + 1):
            revenue *= (1 + self.rev_growth)
            ebitda = revenue * self.ebitda_margin
            capex = revenue * self.capex_pct
            interest = debt_balance * self.interest_rate

            new_wc = revenue * self.wc_pct
            wc_delta = new_wc - wc_balance
            wc_balance = new_wc

            ebt = ebitda - capex - interest - wc_delta
            tax = max(0, ebt) * self.tax_rate
            lfcf_before_debt = ebitda - capex - interest - wc_delta - tax

            if use_sweep:
                principal_repayment = min(lfcf_before_debt, debt_balance)
            else:
                principal_repayment = min(annual_amort, debt_balance)

            debt_balance -= principal_repayment
            lfcf_after_debt = lfcf_before_debt - principal_repayment
            cash_balance += max(0, lfcf_after_debt)  # accumulate cash only if positive
            fcf_list.append(lfcf_after_debt)

            results[f"Year {year}"] = {
                "Revenue": revenue,
                "EBITDA": ebitda,
                "CapEx": capex,
                "Interest": interest,
                "WC Delta": wc_delta,
                "Tax": tax,
                "Principal Repayment": principal_repayment,
                "Ending Debt": debt_balance,
                "Cash Balance": cash_balance,
                "Levered FCF": lfcf_after_debt
            }

        final_ebitda = results[f"Year {years}"]["EBITDA"]
        terminal_value = final_ebitda * self.exit_multiple
        net_debt = debt_balance - cash_balance
        equity_value = terminal_value - net_debt
        irr = self._calc_irr(fcf_list, equity_value)

        results["Exit Summary"] = {
            "Terminal Value": terminal_value,
            "Remaining Debt": debt_balance,
            "Cash Balance": cash_balance,
            "Net Debt": net_debt,
            "Equity Value": equity_value,
            "IRR": irr,
            "MOIC": equity_value / self.equity
        }

        return results

    def _calc_irr(self, fcf_list, terminal_equity):
        cash_flows = [-self.equity] + fcf_list[:-1] + [fcf_list[-1] + terminal_equity]
        return npf.irr(cash_flows)

    @classmethod
    def from_dict(cls, params: Dict[str, float]) -> "LBOModel":
        return cls(**params)
