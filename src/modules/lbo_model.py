import math
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
        revenue_growth_schedule: Optional[List[float]] = None,
        ebitda_margin_schedule: Optional[List[float]] = None,
        ebitda_margin_end: Optional[float] = None,
    ):
        if senior_frac + mezz_frac > 1.0:
            raise ValueError("senior_frac + mezz_frac must ≤ 1.0")

        self.enterprise_value = enterprise_value
        self.debt_pct = debt_pct
        self.revenue0 = revenue
        self.rev_growth = rev_growth
        self.ebitda_margin = ebitda_margin
        self.ebitda_margin_end = (
            ebitda_margin_end if ebitda_margin_end is not None else ebitda_margin
        )
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
        self.revenue_growth_schedule = revenue_growth_schedule
        self.ebitda_margin_schedule = ebitda_margin_schedule

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

    @staticmethod
    def _validate_schedule(name: str, schedule: Optional[List[float]], years: int) -> None:
        if schedule is not None and len(schedule) < years:
            raise ValueError(f"{name} must contain at least {years} values")

    def run(self, years: int = 5, exit_year: Optional[int] = None) -> Dict[str, Any]:
        exit_year = exit_year or years
        self._validate_schedule("revenue_growth_schedule", self.revenue_growth_schedule, years)
        self._validate_schedule("ebitda_margin_schedule", self.ebitda_margin_schedule, years)
        self._validate_schedule("capex_schedule", self.capex_schedule, years)
        self._validate_schedule("da_schedule", self.da_schedule, years)
        self._validate_schedule("wc_schedule", self.wc_schedule, years)

        results: Dict[str, Any] = {}
        irr_cf: List[float] = [-self.equity]

        revenue = self.revenue0
        wc_prev = revenue * self.wc_pct
        opening_nol = 0.0

        for year in range(1, years + 1):
            growth = (
                self.revenue_growth_schedule[year - 1]
                if self.revenue_growth_schedule is not None
                else self.rev_growth
            )
            revenue *= 1 + growth

            if self.ebitda_margin_schedule is not None:
                margin = self.ebitda_margin_schedule[year - 1]
            elif years > 1:
                progress = (year - 1) / (years - 1)
                margin = self.ebitda_margin + (
                    self.ebitda_margin_end - self.ebitda_margin
                ) * progress
            else:
                margin = self.ebitda_margin
            ebitda = revenue * margin

            if self.capex_schedule and len(self.capex_schedule) >= year:
                capex = self.capex_schedule[year - 1]
            else:
                capex = revenue * self.capex_pct

            if self.da_schedule and len(self.da_schedule) >= year:
                da = self.da_schedule[year - 1]
            else:
                da = revenue * self.da_pct

            if self.wc_schedule and len(self.wc_schedule) >= year:
                wc_delta = self.wc_schedule[year - 1]
            else:
                wc_curr = revenue * self.wc_pct
                wc_delta = wc_curr - wc_prev
                wc_prev = wc_curr

            total_interest = sum(t.charge_interest() for t in self.debt_tranches)
            deductible_interest = total_interest

            if self.icr_hurdle and deductible_interest > 0:
                icr = ebitda / deductible_interest
                if icr < self.icr_hurdle:
                    raise CovenantBreachError(f"Year {year}: ICR breach")
            if self.ltv_hurdle is not None and ebitda > 0:
                total_debt = sum(t.debt for t in self.debt_tranches)
                ltv_ratio = total_debt / ebitda
                if ltv_ratio > self.ltv_hurdle:
                    raise CovenantBreachError(
                        f"Year {year}: LTV breach ({ltv_ratio:.1f}x > "
                        f"{self.ltv_hurdle:.1f}x)"
                    )

            ebit = ebitda - da
            ebt = ebit - deductible_interest
            losses_created = max(0.0, -ebt)
            nol_used = min(opening_nol, max(0.0, ebt))
            taxable_income = max(0.0, ebt - nol_used)
            tax = taxable_income * self.tax_rate
            closing_nol = opening_nol + losses_created - nol_used
            net_income = ebt - tax

            cash_available_for_debt_service = net_income + da - capex - wc_delta
            cash_available = max(0.0, cash_available_for_debt_service)

            for t in self.debt_tranches:
                if t.amort and not t.amort_schedule:
                    t.amort_schedule = [t.orig_balance / years] * years

            scheduled_amortization = 0.0
            for t in self.debt_tranches:
                if t.amort and year - 1 < len(t.amort_schedule):
                    due = min(t.amort_schedule[year - 1], t.balance)
                    pay = min(cash_available, due)
                    t.balance -= pay
                    cash_available -= pay
                    scheduled_amortization += pay
                    short = due - pay
                    if short > 1e-8:
                        rev = next((x for x in self.debt_tranches if x.revolver), None)
                        if rev:
                            drawn = rev.draw(short)
                            short -= drawn
                        if short > 1e-8:
                            raise InsolvencyError(
                                f"Year {year}: cannot meet amort on {t.name}"
                            )

            optional_cash_sweep = 0.0
            sweep_budget = cash_available * self.cash_sweep_pct
            sweep_priority = [
                t for t in self.debt_tranches if t.revolver
            ] + [
                t for t in self.debt_tranches if not t.revolver and not t.pik
            ]
            sweep_remaining = sweep_budget
            for tranche in sweep_priority:
                if sweep_remaining <= 0:
                    break
                pay = min(sweep_remaining, tranche.balance)
                tranche.balance = max(0.0, tranche.balance - pay)
                sweep_remaining -= pay
                optional_cash_sweep += pay
            cash_available -= optional_cash_sweep

            ending_cash = cash_available
            equity_distribution = ending_cash

            total_debt = sum(t.debt for t in self.debt_tranches)
            results[f"Year {year}"] = {
                "Revenue": revenue,
                "EBITDA": ebitda,
                "D&A": da,
                "EBIT": ebit,
                "Interest": total_interest,
                "Cash Interest": total_interest,
                "Deductible Interest": deductible_interest,
                "Opening NOL": opening_nol,
                "Losses Created": losses_created,
                "NOL Used": nol_used,
                "Closing NOL": closing_nol,
                "Tax": tax,
                "Net Income": net_income,
                "NOPAT": net_income,
                "CapEx": capex,
                "ΔWC": wc_delta,
                "Cash Available for Debt Service": cash_available_for_debt_service,
                "Levered CF": cash_available_for_debt_service,
                "Scheduled Amortization": scheduled_amortization,
                "Amortization": scheduled_amortization,
                "Optional Cash Sweep": optional_cash_sweep,
                "Cash Distribution / Ending Cash": ending_cash,
                "Ending Cash": ending_cash,
                "Equity CF": equity_distribution,
                "Total Debt": total_debt,
                "Total_Debt": total_debt,
            }
            irr_cf.append(equity_distribution)
            opening_nol = closing_nol

        tv = (
            results[f"Year {exit_year}"]["EBITDA"]
            * self.exit_multiple
            * (1 - self.sale_cost_pct)
        )
        nd = sum(t.debt for t in self.debt_tranches)
        eqv = tv - nd

        # Exit proceeds are realized in the final holding-year cash flow period.
        irr_cf[-1] += eqv

        # FIX: Calculate IRR from complete equity cashflow vector
        irr = float(npf.irr(irr_cf)) if npf is not None else _irr_fallback(irr_cf)
        irr = float(irr) if irr is not None and not math.isnan(irr) else None

        # FIX: MOIC includes all equity returns (interim + exit)
        total_equity_inflows = sum(max(0, cf) for cf in irr_cf[1:])
        moic = total_equity_inflows / self.equity if self.equity > 0 else None

        # Add invariant checks for debugging
        assert irr_cf[0] < 0, f"Initial equity must be negative: {irr_cf[0]}"

        results["Exit Summary"] = {
            "Exit Year": exit_year,
            "Equity Value": eqv,
            "IRR": irr,
            "MOIC": moic,
            "Equity Cash Flow Vector": irr_cf,
        }
        return results