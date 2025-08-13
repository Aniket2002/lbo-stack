import math
from typing import Any, Dict, List, Optional

import numpy_financial as npf


class CovenantBreachError(Exception):
    pass


class InsolvencyError(Exception):
    pass


class DebtTranche:
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
        self.amort_schedule: List[float] = []

    @property
    def debt(self) -> float:
        return self.balance

    def charge_interest(self) -> float:
        interest = self.balance * self.rate
        if self.pik:
            self.balance += interest
        return interest

    def draw(self, amount: float) -> float:
        if not self.revolver:
            return 0.0
        avail = self.revolver_limit - self.balance
        draw_amt = min(avail, amount)
        self.balance += draw_amt
        return draw_amt


class LBOModel:
    def __init__(
        self,
        enterprise_value: float,
        debt_pct: float,
        senior_frac: float,
        mezz_frac: float,
        revenue: float,
        rev_growth: float,
        ebitda_margin: float,
        capex_pct: float,
        wc_pct: float,
        tax_rate: float,
        exit_multiple: float,
        senior_rate: float,
        mezz_rate: float,
        revolver_limit: float = 0.0,
        revolver_rate: float = 0.0,
        pik_rate: float = 0.0,
        ltv_hurdle: Optional[float] = None,
        icr_hurdle: Optional[float] = None,
        da_pct: float = 0.0,
        cash_sweep_pct: float = 1.0,
        sale_cost_pct: float = 0.0,
        capex_schedule: Optional[List[float]] = None,
        da_schedule: Optional[List[float]] = None,
        wc_schedule: Optional[List[float]] = None,
    ):
        if senior_frac + mezz_frac > 1.0:
            raise ValueError("senior_frac + mezz_frac must ≤ 1.0")

        self.enterprise_value = enterprise_value
        self.debt_pct = debt_pct
        self.revenue0 = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.capex_pct = capex_pct
        self.wc_pct = wc_pct
        self.tax_rate = tax_rate
        self.exit_multiple = exit_multiple
        self.ltv_hurdle = ltv_hurdle
        self.icr_hurdle = icr_hurdle
        self.da_pct = da_pct
        self.cash_sweep_pct = cash_sweep_pct
        self.sale_cost_pct = sale_cost_pct

        self.capex_schedule = capex_schedule
        self.da_schedule = da_schedule
        self.wc_schedule = wc_schedule

        total_debt = enterprise_value * debt_pct
        senior_amt = total_debt * senior_frac
        mezz_amt = total_debt * mezz_frac
        bullet_amt = total_debt - senior_amt - mezz_amt
        self.equity = enterprise_value - total_debt

        self.debt_tranches: List[DebtTranche] = [
            DebtTranche("Senior", senior_amt, senior_rate, amort=True),
            DebtTranche("Mezzanine", mezz_amt, mezz_rate, amort=True),
            DebtTranche(
                "Bullet",
                bullet_amt,
                pik_rate if pik_rate > 0 else senior_rate,
                amort=False,
                pik=(pik_rate > 0),
            ),
        ]
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
        exit_year = exit_year or years
        results: Dict[str, Any] = {}
        irr_cf: List[float] = [-self.equity]

        revenue = self.revenue0
        wc_prev = revenue * self.wc_pct

        for year in range(1, years + 1):
            if year > 1:
                revenue *= 1 + self.rev_growth
            ebitda = revenue * self.ebitda_margin

            if self.capex_schedule and len(self.capex_schedule) >= year:
                capex = self.capex_schedule[year - 1]
            else:
                capex = revenue * self.capex_pct

            if self.da_schedule and len(self.da_schedule) >= year:
                da = self.da_schedule[year - 1]
            else:
                da = ebitda * self.da_pct

            if self.wc_schedule and len(self.wc_schedule) >= year:
                wc_delta = self.wc_schedule[year - 1]
            else:
                wc_curr = revenue * self.wc_pct
                wc_delta = wc_curr - wc_prev
                wc_prev = wc_curr

            total_interest = sum(t.charge_interest() for t in self.debt_tranches)

            if self.icr_hurdle and total_interest > 0:
                icr = ebitda / total_interest
                if icr < self.icr_hurdle:
                    raise CovenantBreachError(f"Year {year}: ICR breach")
            # FIX: LTV should be Net Debt / EBITDA ratio, not debt > EV
            if self.ltv_hurdle is not None and ebitda > 0:
                total_debt = sum(t.debt for t in self.debt_tranches)
                ltv_ratio = total_debt / ebitda
                if ltv_ratio > self.ltv_hurdle:
                    raise CovenantBreachError(
                        f"Year {year}: LTV breach ({ltv_ratio:.1f}x > "
                        f"{self.ltv_hurdle:.1f}x)"
                    )

            ebt = ebitda - total_interest
            tax = ebt * self.tax_rate
            nopat = ebt - tax

            lcf = nopat + da - capex - wc_delta
            remaining_cash = lcf

            for t in self.debt_tranches:
                if t.amort and not t.amort_schedule:
                    t.amort_schedule = [t.orig_balance / years] * years

            for t in self.debt_tranches:
                if t.amort and year - 1 < len(t.amort_schedule):
                    due = t.amort_schedule[year - 1]
                    pay = min(remaining_cash, due)
                    t.balance -= pay
                    remaining_cash -= pay
                    short = due - pay
                    if short > 1e-8:
                        rev = next((x for x in self.debt_tranches if x.revolver), None)
                        if rev:
                            rev.draw(short)
                            short = 0.0
                        if short > 1e-8:
                            raise InsolvencyError(
                                f"Year {year}: cannot meet amort on {t.name}"
                            )

            sweep_left = lcf * self.cash_sweep_pct
            for t in self.debt_tranches:
                if t.revolver:
                    pay = min(sweep_left, t.balance)
                    t.balance -= pay
                    sweep_left -= pay
                    if sweep_left <= 0:
                        break
            for t in self.debt_tranches:
                if not t.revolver and not t.pik:
                    pay = min(sweep_left, t.balance)
                    t.balance -= pay
                    sweep_left -= pay
                    if sweep_left <= 0:
                        break
            remaining_cash = lcf - (lcf * self.cash_sweep_pct - sweep_left)

            total_debt = sum(t.debt for t in self.debt_tranches)
            print(
                f"[DEBUG] Year {year} | EBITDA: {ebitda:.2f} | "
                f"Interest: {total_interest:.2f} | "
                f"Equity CF: {remaining_cash:.2f} | "
                f"Total Debt: {total_debt:.2f}"
            )
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

        tv = (
            results[f"Year {exit_year}"]["EBITDA"]
            * self.exit_multiple
            * (1 - self.sale_cost_pct)
        )
        nd = sum(t.debt for t in self.debt_tranches)
        eqv = tv - nd

        # FIX: Add exit equity value to IRR cashflow vector
        irr_cf.append(eqv)

        # FIX: Calculate IRR from complete equity cashflow vector
        irr = npf.irr(irr_cf)
        irr = float(irr) if irr is not None and not math.isnan(irr) else None

        # FIX: MOIC includes all equity returns (interim + exit)
        total_equity_inflows = sum(max(0, cf) for cf in irr_cf[1:])
        moic = total_equity_inflows / self.equity if self.equity > 0 else None

        # Add invariant checks for debugging
        assert irr_cf[0] < 0, f"Initial equity must be negative: {irr_cf[0]}"
        if irr is not None and not math.isnan(irr):
            expected_positive_irr = sum(irr_cf[1:]) > -irr_cf[0]
            if expected_positive_irr and irr < 0:
                print(
                    f"[WARNING] IRR/MOIC mismatch: IRR={irr:.2%}, " f"MOIC={moic:.2f}x"
                )
            if not expected_positive_irr and irr > 0:
                print(
                    f"[WARNING] IRR/MOIC mismatch: IRR={irr:.2%}, " f"MOIC={moic:.2f}x"
                )

        results["Exit Summary"] = {
            "Exit Year": exit_year,
            "Equity Value": eqv,
            "IRR": irr,
            "MOIC": moic,
        }
        return results