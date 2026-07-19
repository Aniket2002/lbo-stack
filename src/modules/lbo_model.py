from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import numpy_financial as npf
except ImportError:  # pragma: no cover
    npf = None


class CovenantBreachError(Exception):
    """Raised when an enabled financial covenant is breached."""


class InsolvencyError(Exception):
    """Raised when liquidity or mandatory debt service cannot be funded."""


def _irr_fallback(cashflows: List[float]) -> float:
    if len(cashflows) < 2 or not any(value < 0 for value in cashflows):
        return float("nan")
    if not any(value > 0 for value in cashflows):
        return float("nan")

    rate = 0.10
    for _ in range(200):
        if rate <= -0.999999:
            rate = -0.999999

        npv = 0.0
        derivative = 0.0
        for period, cashflow in enumerate(cashflows):
            denominator = (1.0 + rate) ** period
            npv += cashflow / denominator
            if period:
                derivative -= (
                    period * cashflow / (1.0 + rate) ** (period + 1)
                )

        if abs(npv) < 1e-10:
            return rate
        if abs(derivative) < 1e-12:
            break

        next_rate = rate - npv / derivative
        if not math.isfinite(next_rate):
            break
        if abs(next_rate - rate) < 1e-10:
            return next_rate
        rate = next_rate

    return float("nan")


def calculate_irr(cashflows: List[float]) -> Optional[float]:
    try:
        value = (
            float(npf.irr(cashflows))
            if npf is not None
            else _irr_fallback(cashflows)
        )
    except (ValueError, TypeError, OverflowError, FloatingPointError):
        return None

    return value if math.isfinite(value) else None


@dataclass
class DebtTranche:
    name: str
    balance: float
    rate: float
    amort: bool = False
    revolver: bool = False
    revolver_limit: float = 0.0
    pik: bool = False
    sweepable: bool = True
    amort_schedule: List[float] = field(default_factory=list)
    orig_balance: float = field(init=False)

    def __post_init__(self) -> None:
        if self.balance < 0:
            raise ValueError(f"{self.name}: balance cannot be negative")
        if self.rate < 0:
            raise ValueError(f"{self.name}: rate cannot be negative")
        if self.revolver_limit < 0:
            raise ValueError(f"{self.name}: revolver limit cannot be negative")
        if self.revolver and self.balance > self.revolver_limit + 1e-9:
            raise ValueError(f"{self.name}: balance exceeds revolver limit")
        self.orig_balance = float(self.balance)

    @property
    def debt(self) -> float:
        return self.balance

    def accrue_interest(self) -> tuple[float, float]:
        """Return cash and PIK interest, capitalising only PIK interest."""
        interest = self.balance * self.rate
        if self.pik:
            self.balance += interest
            return 0.0, interest
        return interest, 0.0

    def draw(self, amount: float) -> float:
        if amount <= 0 or not self.revolver:
            return 0.0
        available = max(0.0, self.revolver_limit - self.balance)
        draw_amount = min(available, amount)
        self.balance += draw_amount
        return draw_amount


class LBOModel:
    """Annual LBO model with an explicit cash and debt waterfall."""

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
        min_cash: float = 0.0,
        sale_cost_pct: float = 0.0,
        capex_schedule: Optional[List[float]] = None,
        da_schedule: Optional[List[float]] = None,
        wc_schedule: Optional[List[float]] = None,
        revenue_growth_schedule: Optional[List[float]] = None,
        ebitda_margin_schedule: Optional[List[float]] = None,
        ebitda_margin_end: Optional[float] = None,
        initial_equity: Optional[float] = None,
        opening_cash: float = 0.0,
    ) -> None:
        if enterprise_value <= 0:
            raise ValueError("enterprise_value must be positive")
        if not 0 <= debt_pct <= 1:
            raise ValueError("debt_pct must be between 0 and 1")
        if senior_frac < 0 or mezz_frac < 0 or senior_frac + mezz_frac > 1:
            raise ValueError("senior_frac and mezz_frac must be non-negative and sum to <= 1")
        if revenue <= 0:
            raise ValueError("revenue must be positive")
        if not 0 <= tax_rate <= 1:
            raise ValueError("tax_rate must be between 0 and 1")
        if not 0 <= cash_sweep_pct <= 1:
            raise ValueError("cash_sweep_pct must be between 0 and 1")
        if min_cash < 0 or opening_cash < 0:
            raise ValueError("cash balances cannot be negative")
        if sale_cost_pct < 0 or sale_cost_pct >= 1:
            raise ValueError("sale_cost_pct must be between 0 and 1")

        self.enterprise_value = float(enterprise_value)
        self.debt_pct = float(debt_pct)
        self.revenue0 = float(revenue)
        self.rev_growth = float(rev_growth)
        self.ebitda_margin = float(ebitda_margin)
        self.ebitda_margin_end = float(
            ebitda_margin if ebitda_margin_end is None else ebitda_margin_end
        )
        self.capex_pct = float(capex_pct)
        self.wc_pct = float(wc_pct)
        self.tax_rate = float(tax_rate)
        self.exit_multiple = float(exit_multiple)
        self.ltv_hurdle = ltv_hurdle
        self.icr_hurdle = icr_hurdle
        self.da_pct = float(da_pct)
        self.cash_sweep_pct = float(cash_sweep_pct)
        self.min_cash = float(min_cash)
        self.sale_cost_pct = float(sale_cost_pct)
        self.capex_schedule = capex_schedule
        self.da_schedule = da_schedule
        self.wc_schedule = wc_schedule
        self.revenue_growth_schedule = revenue_growth_schedule
        self.ebitda_margin_schedule = ebitda_margin_schedule
        self.opening_cash = float(opening_cash)

        total_financial_debt = self.enterprise_value * self.debt_pct
        senior_amount = total_financial_debt * senior_frac
        mezz_amount = total_financial_debt * mezz_frac
        bullet_amount = total_financial_debt - senior_amount - mezz_amount

        fallback_equity = self.enterprise_value - total_financial_debt
        self.equity = float(
            fallback_equity if initial_equity is None else initial_equity
        )
        if self.equity <= 0:
            raise ValueError("initial equity must be positive")

        self.debt_tranches: List[DebtTranche] = [
            DebtTranche(
                name="Senior",
                balance=senior_amount,
                rate=senior_rate,
                amort=True,
            ),
            DebtTranche(
                name="Mezzanine",
                balance=mezz_amount,
                rate=mezz_rate,
                amort=True,
            ),
            DebtTranche(
                name="Bullet",
                balance=bullet_amount,
                rate=pik_rate if pik_rate > 0 else senior_rate,
                amort=False,
                pik=pik_rate > 0,
                sweepable=pik_rate <= 0,
            ),
        ]

        if revolver_limit > 0:
            self.debt_tranches.append(
                DebtTranche(
                    name="Revolver",
                    balance=0.0,
                    rate=revolver_rate,
                    revolver=True,
                    revolver_limit=revolver_limit,
                    sweepable=True,
                )
            )

    @staticmethod
    def _validate_schedule(
        name: str,
        schedule: Optional[List[float]],
        horizon: int,
    ) -> None:
        if schedule is not None and len(schedule) < horizon:
            raise ValueError(f"{name} must contain at least {horizon} values")

    def _revolver(self) -> Optional[DebtTranche]:
        return next(
            (tranche for tranche in self.debt_tranches if tranche.revolver),
            None,
        )

    def _prepare_amortisation(self, horizon: int) -> None:
        for tranche in self.debt_tranches:
            if tranche.amort and not tranche.amort_schedule:
                tranche.amort_schedule = [tranche.orig_balance / horizon] * horizon

    def run(
        self,
        years: int = 5,
        exit_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        if years <= 0:
            raise ValueError("years must be positive")

        horizon = years if exit_year is None else exit_year
        if horizon <= 0 or horizon > years:
            raise ValueError("exit_year must be between 1 and years")

        for name, schedule in (
            ("revenue_growth_schedule", self.revenue_growth_schedule),
            ("ebitda_margin_schedule", self.ebitda_margin_schedule),
            ("capex_schedule", self.capex_schedule),
            ("da_schedule", self.da_schedule),
            ("wc_schedule", self.wc_schedule),
        ):
            self._validate_schedule(name, schedule, horizon)

        self._prepare_amortisation(horizon)

        results: Dict[str, Any] = {}
        equity_cashflows: List[float] = [-self.equity]
        revenue = self.revenue0
        previous_working_capital = revenue * self.wc_pct
        opening_nol = 0.0
        opening_cash = self.opening_cash
        revolver = self._revolver()

        for year in range(1, horizon + 1):
            opening_debt = sum(tranche.balance for tranche in self.debt_tranches)

            growth = (
                self.revenue_growth_schedule[year - 1]
                if self.revenue_growth_schedule is not None
                else self.rev_growth
            )
            revenue *= 1.0 + growth

            if self.ebitda_margin_schedule is not None:
                margin = self.ebitda_margin_schedule[year - 1]
            elif horizon > 1:
                progress = (year - 1) / (horizon - 1)
                margin = self.ebitda_margin + (
                    self.ebitda_margin_end - self.ebitda_margin
                ) * progress
            else:
                margin = self.ebitda_margin_end

            ebitda = revenue * margin
            capex = (
                self.capex_schedule[year - 1]
                if self.capex_schedule is not None
                else revenue * self.capex_pct
            )
            depreciation = (
                self.da_schedule[year - 1]
                if self.da_schedule is not None
                else revenue * self.da_pct
            )

            if self.wc_schedule is not None:
                working_capital_change = self.wc_schedule[year - 1]
            else:
                current_working_capital = revenue * self.wc_pct
                working_capital_change = (
                    current_working_capital - previous_working_capital
                )
                previous_working_capital = current_working_capital

            cash_interest = 0.0
            pik_interest = 0.0
            for tranche in self.debt_tranches:
                tranche_cash_interest, tranche_pik_interest = (
                    tranche.accrue_interest()
                )
                cash_interest += tranche_cash_interest
                pik_interest += tranche_pik_interest
            total_interest = cash_interest + pik_interest

            icr = math.inf if cash_interest <= 1e-12 else ebitda / cash_interest
            if self.icr_hurdle is not None and icr < self.icr_hurdle:
                raise CovenantBreachError(
                    f"Year {year}: ICR breach ({icr:.2f}x < "
                    f"{self.icr_hurdle:.2f}x)"
                )

            if self.ltv_hurdle is not None and ebitda > 0:
                gross_leverage = (
                    sum(tranche.balance for tranche in self.debt_tranches)
                    / ebitda
                )
                if gross_leverage > self.ltv_hurdle:
                    raise CovenantBreachError(
                        f"Year {year}: leverage breach "
                        f"({gross_leverage:.2f}x > {self.ltv_hurdle:.2f}x)"
                    )

            ebit = ebitda - depreciation
            ebt = ebit - total_interest
            losses_created = max(0.0, -ebt)
            nol_used = min(opening_nol, max(0.0, ebt))
            taxable_income = max(0.0, ebt - nol_used)
            cash_tax = taxable_income * self.tax_rate
            closing_nol = opening_nol + losses_created - nol_used
            net_income = ebt - cash_tax

            operating_cash_generation = (
                ebitda
                - cash_interest
                - cash_tax
                - capex
                - working_capital_change
            )
            cash_before_financing = opening_cash + operating_cash_generation

            operating_revolver_draw = 0.0
            operating_deficit = max(0.0, self.min_cash - cash_before_financing)
            if operating_deficit > 1e-8:
                if revolver is None:
                    raise InsolvencyError(
                        f"Year {year}: operating cash deficit with no revolver"
                    )
                operating_revolver_draw = revolver.draw(operating_deficit)
                cash_before_financing += operating_revolver_draw
                if cash_before_financing < self.min_cash - 1e-8:
                    raise InsolvencyError(
                        f"Year {year}: revolver insufficient to maintain "
                        "minimum cash"
                    )

            cash_before_debt_service = cash_before_financing
            scheduled_amortisation = 0.0
            cash_funded_amortisation = 0.0
            revolver_funded_amortisation = 0.0
            actual_amortisation = 0.0
            unpaid_principal = 0.0

            for tranche in self.debt_tranches:
                if not tranche.amort or year - 1 >= len(tranche.amort_schedule):
                    continue

                due = min(tranche.amort_schedule[year - 1], tranche.balance)
                scheduled_amortisation += due

                cash_above_minimum = max(
                    0.0,
                    cash_before_financing - self.min_cash,
                )
                cash_paid = min(due, cash_above_minimum)
                tranche.balance -= cash_paid
                cash_before_financing -= cash_paid
                cash_funded_amortisation += cash_paid
                actual_amortisation += cash_paid

                shortfall = due - cash_paid
                if shortfall > 1e-8 and revolver is not None:
                    revolver_paid = revolver.draw(shortfall)
                    tranche.balance -= revolver_paid
                    revolver_funded_amortisation += revolver_paid
                    actual_amortisation += revolver_paid
                    shortfall -= revolver_paid

                if shortfall > 1e-8:
                    unpaid_principal += shortfall

            payment_default = unpaid_principal > 1e-8
            if payment_default:
                raise InsolvencyError(
                    f"Year {year}: unpaid mandatory principal of "
                    f"{unpaid_principal:.2f}"
                )

            sweep_budget = (
                max(0.0, cash_before_financing - self.min_cash)
                * self.cash_sweep_pct
            )
            sweep_remaining = sweep_budget
            optional_cash_sweep = 0.0

            sweep_priority = [
                tranche
                for tranche in self.debt_tranches
                if tranche.revolver and tranche.sweepable
            ] + [
                tranche
                for tranche in self.debt_tranches
                if (
                    not tranche.revolver
                    and not tranche.pik
                    and tranche.sweepable
                )
            ]

            for tranche in sweep_priority:
                if sweep_remaining <= 1e-8:
                    break
                payment = min(sweep_remaining, tranche.balance)
                tranche.balance -= payment
                sweep_remaining -= payment
                optional_cash_sweep += payment

            ending_cash = cash_before_financing - optional_cash_sweep
            if ending_cash < self.min_cash - 1e-8:
                raise AssertionError(
                    f"Year {year}: ending cash fell below minimum cash"
                )

            total_revolver_draws = (
                operating_revolver_draw + revolver_funded_amortisation
            )
            debt_repayments = actual_amortisation + optional_cash_sweep
            closing_debt = sum(
                tranche.balance for tranche in self.debt_tranches
            )

            debt_roll_forward_formula = (
                opening_debt
                + total_revolver_draws
                + pik_interest
                - debt_repayments
            )
            debt_roll_forward_delta = (
                debt_roll_forward_formula - closing_debt
            )
            if abs(debt_roll_forward_delta) > 1e-8:
                raise AssertionError(
                    f"Year {year}: debt roll-forward failed by "
                    f"{debt_roll_forward_delta:.10f}"
                )

            cash_roll_forward_formula = (
                opening_cash
                + operating_cash_generation
                + operating_revolver_draw
                - cash_funded_amortisation
                - optional_cash_sweep
            )
            cash_roll_forward_delta = cash_roll_forward_formula - ending_cash
            if abs(cash_roll_forward_delta) > 1e-8:
                raise AssertionError(
                    f"Year {year}: cash roll-forward failed by "
                    f"{cash_roll_forward_delta:.10f}"
                )

            equity_distribution = 0.0
            equity_cashflows.append(equity_distribution)

            results[f"Year {year}"] = {
                "Opening Cash": opening_cash,
                "Opening Debt": opening_debt,
                "Revenue": revenue,
                "Revenue Growth": growth,
                "EBITDA Margin": margin,
                "EBITDA": ebitda,
                "D&A": depreciation,
                "EBIT": ebit,
                "Cash Interest": cash_interest,
                "PIK Interest": pik_interest,
                "Total Interest": total_interest,
                "Interest": total_interest,
                "ICR": icr,
                "Opening NOL": opening_nol,
                "Losses Created": losses_created,
                "NOL Used": nol_used,
                "Closing NOL": closing_nol,
                "Taxable Income": taxable_income,
                "Cash Tax": cash_tax,
                "Tax": cash_tax,
                "Net Income": net_income,
                "CapEx": capex,
                "ΔWC": working_capital_change,
                "Operating Cash Generation": operating_cash_generation,
                "Cash Available for Debt Service": operating_cash_generation,
                "Levered CF": operating_cash_generation,
                "Operating Deficit": operating_deficit,
                "Operating Revolver Draw": operating_revolver_draw,
                "Cash Before Debt Service": cash_before_debt_service,
                "Scheduled Amortization": scheduled_amortisation,
                "Cash-Funded Amortization": cash_funded_amortisation,
                "Revolver-Funded Amortization": (
                    revolver_funded_amortisation
                ),
                "Actual Amortization": actual_amortisation,
                "Amortization": actual_amortisation,
                "Unpaid Principal": unpaid_principal,
                "Payment Default": payment_default,
                "Optional Cash Sweep": optional_cash_sweep,
                "Debt Draws": total_revolver_draws,
                "Revolver Draws": total_revolver_draws,
                "Debt Repayments": debt_repayments,
                "Ending Cash": ending_cash,
                "Closing Cash": ending_cash,
                "Minimum Cash": self.min_cash,
                "Equity CF": equity_distribution,
                "Closing Debt": closing_debt,
                "Total Debt": closing_debt,
                "Total_Debt": closing_debt,
                "Debt Roll-Forward Formula": debt_roll_forward_formula,
                "Debt Roll-Forward Delta": debt_roll_forward_delta,
                "Cash Roll-Forward Formula": cash_roll_forward_formula,
                "Cash Roll-Forward Delta": cash_roll_forward_delta,
            }

            opening_cash = ending_cash
            opening_nol = closing_nol

        final_year = results[f"Year {horizon}"]
        exit_enterprise_value = final_year["EBITDA"] * self.exit_multiple
        sale_costs = exit_enterprise_value * self.sale_cost_pct
        final_debt = final_year["Closing Debt"]
        final_cash = final_year["Ending Cash"]
        exit_equity = (
            exit_enterprise_value - sale_costs - final_debt + final_cash
        )

        equity_cashflows[-1] += exit_equity
        irr = calculate_irr(equity_cashflows)
        total_equity_inflows = sum(max(0.0, value) for value in equity_cashflows[1:])
        moic = total_equity_inflows / self.equity

        results["Exit Summary"] = {
            "Exit Year": horizon,
            "Exit Enterprise Value": exit_enterprise_value,
            "Sale Costs": sale_costs,
            "Final Debt": final_debt,
            "Final Cash": final_cash,
            "Equity Value": exit_equity,
            "IRR": irr,
            "MOIC": moic,
            "Initial Equity": self.equity,
            "Equity Cash Flow Vector": equity_cashflows,
        }
        return results

    def summary(self, years: int = 5) -> str:
        results = self.run(years=years)
        exit_summary = results["Exit Summary"]
        irr = exit_summary["IRR"]
        irr_text = "n/a" if irr is None else f"{irr:.2%}"
        return (
            f"Exit Year: {exit_summary['Exit Year']}\n"
            f"Equity Value: {exit_summary['Equity Value']:.2f}\n"
            f"IRR: {irr_text}\n"
            f"MOIC: {exit_summary['MOIC']:.2f}x"
        )
