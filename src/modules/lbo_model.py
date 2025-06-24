# src/modules/lbo_model.py
from typing import List, Optional, Dict, Any
import numpy as np
import numpy_financial as npf


class CovenantBreachError(Exception):
    """Raised when a covenant (ICR or LTV) is breached."""
    pass


class InsolvencyError(Exception):
    """Raised when the company runs out of cash (cannot service debt)."""
    pass


class DebtTranche:
    def __init__(
        self,
        name: str,
        principal: float,
        rate: float,
        amort_schedule: Optional[List[float]] = None,
        revolver: bool = False,
        revolver_limit: float = 0.0,
        pik: bool = False
    ):
        self.name = name
        self.rate = rate
        self.amort_schedule = amort_schedule or []
        self.revolver = revolver
        self.limit = revolver_limit
        self.pik = pik
        self.balance = principal

    def charge_interest(self) -> float:
        interest_due = self.balance * self.rate
        if self.pik:
            # PIK: capitalize interest instead of cash pay
            self.balance += interest_due
            return 0.0
        return interest_due

    def repay_principal(self, cash_available: float, year_idx: int) -> float:
        """Repay scheduled principal for this tranche."""
        if self.amort_schedule and year_idx < len(self.amort_schedule):
            due = self.amort_schedule[year_idx]
            paid = min(due, cash_available)
            self.balance -= paid
            return paid
        return 0.0

    def draw(self, amount: float) -> float:
        """Draw from revolver up to its limit to cover shortfalls."""
        if not self.revolver:
            raise ValueError(f"{self.name} is not a revolver tranche")
        available = self.limit - self.balance
        draw_amt = min(amount, available)
        self.balance += draw_amt
        return draw_amt

    @property
    def debt(self) -> float:
        return self.balance


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
        interest_rate: float,
        da_pct: float = 0.0,
        revolver_limit: float = 0.0,
        revolver_rate: float = 0.0,
        pik_rate: float = 0.0,
        icr_hurdle: Optional[float] = None,
        ltv_hurdle: Optional[float] = None,
        cash_sweep_pct: float = 1.0
    ):
        # Core deal assumptions
        self.enterprise_value = enterprise_value
        self.revenue0 = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.capex_pct = capex_pct
        self.wc_pct = wc_pct
        self.tax_rate = tax_rate
        self.exit_multiple = exit_multiple
        self.da_pct = da_pct
        self.cash_sweep_pct = cash_sweep_pct

        # Build debt tranches
        total_debt = enterprise_value * debt_pct
        bullet_amt = total_debt * 0.7
        amort_amt  = total_debt * 0.3
        amort_schedule = [amort_amt / 5] * 5

        self.debt_tranches: List[DebtTranche] = [
            DebtTranche("Bullet", principal=bullet_amt, rate=interest_rate),
            DebtTranche("Amortizing", principal=amort_amt, rate=interest_rate, amort_schedule=amort_schedule)
        ]
        if revolver_limit > 0:
            # Revolver starts at zero drawn
            self.debt_tranches.append(
                DebtTranche("Revolver", principal=0.0, rate=revolver_rate,
                            revolver=True, revolver_limit=revolver_limit)
            )
        if pik_rate > 0:
            self.debt_tranches.append(
                DebtTranche("PIK", principal=0.0, rate=pik_rate, pik=True)
            )

        # Covenant thresholds
        self.icr_hurdle = icr_hurdle
        self.ltv_hurdle = ltv_hurdle

        # Equity investment
        self.equity = enterprise_value - total_debt

    def run(self, years: int = 5, exit_year: Optional[int] = None) -> Dict[str, Any]:
        exit_year = exit_year or years
        results: Dict[str, Any] = {}
        irr_cf: List[float] = [-self.equity]

        revenue = self.revenue0
        wc_prev  = revenue * self.wc_pct

        for year in range(1, years + 1):
            # 1. Revenue & EBITDA
            if year > 1:
                revenue *= (1 + self.rev_growth)
            ebitda = revenue * self.ebitda_margin

            # 2. Depreciation & EBIT
            da   = revenue * self.da_pct
            ebit = ebitda - da

            # 3. Charge interest (PIK capitalizes)
            total_interest = sum(t.charge_interest() for t in self.debt_tranches)

            # ICR covenant
            if self.icr_hurdle and total_interest > 0:
                icr = ebitda / total_interest
                if icr < self.icr_hurdle:
                    raise CovenantBreachError(f"Year {year}: ICR {icr:.2f} below {self.icr_hurdle}")

            # 4. Tax
            ebt = ebit - total_interest
            tax = max(0.0, ebt * self.tax_rate)

            # 5. NOPAT & Unlevered FCF
            nopat   = ebt - tax
            wc_curr = revenue * self.wc_pct
            wc_delta= wc_curr - wc_prev
            wc_prev = wc_curr
            capex   = revenue * self.capex_pct
            ufcf    = nopat + da - capex - wc_delta

            cash_avail = ufcf

            # 6. Scheduled principal repayment
            for t in self.debt_tranches:
                paid = t.repay_principal(cash_avail, year - 1)
                cash_avail -= paid

            # 7. Cash sweep of excess
            sweep_amt = cash_avail * self.cash_sweep_pct
            for t in self.debt_tranches:
                if not (t.revolver or t.pik):
                    pay = min(t.debt, sweep_amt)
                    t.balance -= pay
                    cash_avail -= pay
                    break

            # 8. Revolver auto-draw if shortfall
            if cash_avail < 0:
                rev = next((t for t in self.debt_tranches if t.revolver), None)
                if rev:
                    draw_amount = rev.draw(-cash_avail)
                    cash_avail += draw_amount

            # 9. Insolvency check
            if cash_avail < 0:
                raise InsolvencyError(f"Year {year}: Cash shortfall of {cash_avail:.2f}")

            # 10. Record equity cash flow
            irr_cf.append(cash_avail)

            # LTV covenant
            total_debt = sum(t.debt for t in self.debt_tranches)
            if self.ltv_hurdle and ebitda > 0:
                ltv = total_debt / ebitda
                if ltv > self.ltv_hurdle:
                    raise CovenantBreachError(f"Year {year}: LTV {ltv:.2f} above {self.ltv_hurdle}")

            # Save year results
            results[f"Year {year}"] = {
                "Revenue": revenue,
                "EBITDA": ebitda,
                "D&A": da,
                "EBIT": ebit,
                "Interest": total_interest,
                "Tax": tax,
                "NOPAT": nopat,
                "CapEx": capex,
                "ΔWC": wc_delta,
                "UFCF": ufcf,
                "Equity CF": cash_avail,
                "Total Debt": total_debt
            }

        # Terminal value at chosen exit_year
        tv_ebitda      = results[f"Year {exit_year}"]["EBITDA"]
        terminal_value = tv_ebitda * self.exit_multiple
        net_debt       = sum(t.debt for t in self.debt_tranches)
        eq_value       = terminal_value - net_debt
        irr_cf.append(eq_value)

        irr  = npf.irr(irr_cf)
        moic = sum(irr_cf[1:]) / self.equity

        results["Exit Summary"] = {
            "Exit Year": exit_year,
            "Terminal Value": terminal_value,
            "Net Debt": net_debt,
            "Equity Value": eq_value,
            "IRR": irr,
            "MOIC": moic
        }
        return results

    def summary(self) -> str:
        es = self.run()["Exit Summary"]
        return (
            f"Exit Year: {es['Exit Year']}\\n"
            f"Equity Value: ${es['Equity Value']:,.0f}\\n"
            f"IRR: {es['IRR']:.2%}\\n"
            f"MOIC: {es['MOIC']:.2f}x\\n"
        )

