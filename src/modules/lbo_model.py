"""
LBOModel: simple leveraged buyout cashflow model.
"""

import math
from typing import Any, Dict, List, Optional

import numpy_financial as npf


class CovenantBreachError(Exception):
    """Raised when an interest or LTV covenant is breached."""


class InsolvencyError(Exception):
    """Raised when the company cannot meet its debt service obligations."""


class DebtTranche:
    """
    Represents a debt tranche.

    Attributes:
        name: descriptive name
        balance: current principal balance
        rate: interest rate per period
        amort: whether this tranche amortizes
        revolver: whether this is a revolver facility
        revolver_limit: max revolver capacity
        pik: whether interest is PIK (accrues to principal)
        orig_balance: initial principal for default amort schedules
        amort_schedule: list of amortization amounts per year
    """

    def __init__(
        self,
        name: str,
        balance: float,
        rate: float,
        amort: bool = False,
        revolver: bool = False,
        revolver_limit: float = 0.0,
        pik: bool = False,
    ):
        self.name = name
        self.balance = balance
        self.rate = rate
        self.amort = amort
        self.revolver = revolver
        self.revolver_limit = revolver_limit
        self.pik = pik
        self.orig_balance = balance
        # Always a list; empty means "use default schedule"
        self.amort_schedule: List[float] = []

    @property
    def debt(self) -> float:
        return self.balance

    def charge_interest(self) -> float:
        """
        Calculate interest expense. For PIK interest, accrues to balance;
        otherwise it's a cash expense. Returns the interest amount.
        """
        interest = self.balance * self.rate
        if self.pik:
            # accrue to principal
            self.balance += interest
        return interest

    def draw(self, amount: float) -> float:
        """
        Draw from revolver up to its limit. Returns the actual drawn amount.
        """
        if not self.revolver:
            return 0.0
        available = self.revolver_limit - self.balance
        draw_amt = min(available, amount)
        self.balance += draw_amt
        return draw_amt


class LBOModel:
    """
    A simple Leveraged Buyout (LBO) cashflow model.

    Example:
        model = LBOModel(
            enterprise_value=100.0,
            debt_pct=0.6,
            revenue=50.0,
            rev_growth=0.1,
            ebitda_margin=0.2,
            capex_pct=0.05,
            wc_pct=0.1,
            tax_rate=0.25,
            exit_multiple=8.0,
            interest_rate=0.07,
            revolver_limit=20.0,
            revolver_rate=0.05,
            pik_rate=0.02,
        )
        results = model.run(years=5)
        print(results["Exit Summary"])
    """

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
        revolver_limit: float = 0.0,
        revolver_rate: float = 0.0,
        pik_rate: float = 0.0,
        bullet_frac: float = 0.7,
        amort_frac: float = 0.3,
        ltv_hurdle: Optional[float] = None,
        icr_hurdle: Optional[float] = None,
        da_pct: float = 0.0,
        cash_sweep_pct: float = 1.0,
        sale_cost_pct: float = 0.0,
    ):
        # Validate that debt fractions sum ≤ 1
        if bullet_frac + amort_frac > 1.0:
            raise ValueError(
                f"bullet_frac + amort_frac must ≤ 1.0, got {bullet_frac + amort_frac}"
            )

        self.enterprise_value = enterprise_value
        self.debt_pct = debt_pct
        self.revenue0 = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.capex_pct = capex_pct
        self.wc_pct = wc_pct
        self.tax_rate = tax_rate
        self.exit_multiple = exit_multiple
        self.interest_rate = interest_rate
        self.revolver_limit = revolver_limit
        self.revolver_rate = revolver_rate
        self.pik_rate = pik_rate
        self.ltv_hurdle = ltv_hurdle
        self.icr_hurdle = icr_hurdle
        self.da_pct = da_pct
        self.cash_sweep_pct = cash_sweep_pct
        self.sale_cost_pct = sale_cost_pct

        total_debt = enterprise_value * debt_pct
        bullet_amt = total_debt * bullet_frac
        amort_amt = total_debt * amort_frac
        self.equity = enterprise_value - total_debt

        # Build debt tranches
        self.debt_tranches: List[DebtTranche] = []

        # Bullet tranche (PIK if requested)
        self.debt_tranches.append(
            DebtTranche(
                "Bullet",
                bullet_amt,
                pik_rate if pik_rate > 0 else interest_rate,
                amort=False,
                pik=(pik_rate > 0),
            )
        )
        # Amortizing tranche
        self.debt_tranches.append(
            DebtTranche(
                "Amortizing",
                amort_amt,
                interest_rate,
                amort=True,
            )
        )
        # Revolver tranche
        if revolver_limit > 0:
            self.debt_tranches.append(
                DebtTranche(
                    "Revolver",
                    0.0,
                    revolver_rate,
                    revolver=True,
                    revolver_limit=revolver_limit,
                )
            )

    def run(self, years: int = 5, exit_year: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the LBO model for `years` periods.

        Returns:
            A dict with keys "Year 1", ..., "Exit Summary".
        """
        exit_year = exit_year or years
        results: Dict[str, Any] = {}
        irr_cf: List[float] = [-self.equity]

        revenue = self.revenue0
        wc_prev = revenue * self.wc_pct

        for year in range(1, years + 1):
            # 1) Revenue & EBITDA
            if year > 1:
                revenue *= 1 + self.rev_growth
            ebitda = revenue * self.ebitda_margin

            # 2) Charge interest (cash + PIK accrual)
            total_interest = sum(t.charge_interest() for t in self.debt_tranches)

            # 3) Covenants
            if self.icr_hurdle and total_interest > 0:
                icr = ebitda / total_interest
                if icr < self.icr_hurdle:
                    raise CovenantBreachError(
                        f"Year {year}: ICR {icr: .2f} below {self.icr_hurdle}"
                    )
            if self.ltv_hurdle is not None:
                current_ev = ebitda * self.exit_multiple
                total_debt = sum(t.debt for t in self.debt_tranches)
                if total_debt > current_ev:
                    raise CovenantBreachError(
                        f"Year {year}: LTV breach—debt {total_debt: .2f} > EV×multiple "
                        f"{current_ev: .2f}"
                    )

            # 4) Tax & levered CF
            ebt = ebitda - total_interest
            tax = max(0.0, ebt * self.tax_rate)
            nopat = ebt - tax

            da = ebitda * self.da_pct
            wc_curr = revenue * self.wc_pct
            wc_delta = wc_curr - wc_prev
            wc_prev = wc_curr
            capex = revenue * self.capex_pct

            # Levered cash flow (LFCF)
            lcf = nopat + da - capex - wc_delta
            remaining_cash = lcf

            # 5) Build default amort schedule if none provided
            for t in self.debt_tranches:
                if t.amort and not t.amort_schedule:
                    t.amort_schedule = [t.orig_balance / years] * years

            # 6) Scheduled amort + revolver draw
            for t in self.debt_tranches:
                if t.amort and (year - 1) < len(t.amort_schedule):
                    due = t.amort_schedule[year - 1]
                    pay = min(remaining_cash, due)
                    t.balance -= pay
                    remaining_cash -= pay
                    short = due - pay
                    if short > 1e-8:
                        rev = next((x for x in self.debt_tranches if x.revolver), None)
                        if rev:
                            drawn = rev.draw(short)
                            short -= drawn
                        if short > 1e-8:
                            raise InsolvencyError(
                                f"Year {year}: cannot meet scheduled amort on {t.name}"
                            )

            # 7) Cash sweep: revolver first, then non‐PIK amort tranches
            total_sweep = lcf * self.cash_sweep_pct
            sweep_left = total_sweep
            # revolver pay‐down
            for t in self.debt_tranches:
                if t.revolver:
                    pay = min(sweep_left, t.balance)
                    t.balance -= pay
                    sweep_left -= pay
                    if sweep_left <= 0:
                        break
            # then non‐revolver, non‐PIK
            for t in self.debt_tranches:
                if not t.revolver and not t.pik:
                    pay = min(sweep_left, t.balance)
                    t.balance -= pay
                    sweep_left -= pay
                    if sweep_left <= 0:
                        break
            cash_paid = total_sweep - sweep_left
            remaining_cash = lcf - cash_paid

            # 8) Record this year
            total_debt = sum(t.debt for t in self.debt_tranches)
            results[f"Year {year}"] = {
                "Revenue": revenue,
                "EBITDA": ebitda,
                "Interest": total_interest,
                "Tax": tax,
                "NOPAT": nopat,
                "D&A": da,
                "CapEx": capex,
                "ΔWC": wc_delta,
                "Levered CF": lcf,
                "Equity CF": remaining_cash,
                "Total Debt": total_debt,
            }
            irr_cf.append(remaining_cash)

        # 9) Exit valuation, apply sale costs
        tv_ebitda = results[f"Year {exit_year}"]["EBITDA"]
        terminal_value = tv_ebitda * self.exit_multiple * (1 - self.sale_cost_pct)
        net_debt = sum(t.debt for t in self.debt_tranches)
        equity_value = terminal_value - net_debt

        irr_cf.append(equity_value)

        # 10) Final IRR & MOIC
        raw_irr = npf.irr(irr_cf)
        irr_final = (
            float(raw_irr)
            if (raw_irr is not None and not math.isnan(raw_irr))
            else None
        )
        moic_final = equity_value / self.equity if self.equity > 0 else 0.0

        results["Exit Summary"] = {
            "Exit Year": exit_year,
            "Equity Value": equity_value,
            "IRR": irr_final,
            "MOIC": moic_final,
        }
        return results

    def summary(self) -> str:
        """
        Return a human-readable summary of the exit metrics.
        """
        es = self.run()["Exit Summary"]
        return (
            f"Exit Year: {es['Exit Year']}\n"
            f"Equity Value: ${es['Equity Value']: , .0f}\n"
            f"IRR: {es['IRR']: .2%}\n"
            f"MOIC: {es['MOIC']: .2f}x\n"
        )
