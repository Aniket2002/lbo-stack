#!/usr/bin/env python3

import os
import sys

# Import classes
from src.modules.orchestrator_advanced import (
    read_accor_assumptions,
    run_enhanced_base_case,
)

assumptions = read_accor_assumptions()

# Run base case
print("Running base case with current assumptions...")
results, metrics = run_enhanced_base_case(assumptions)

print(f'IRR: {metrics.get("IRR", "N/A")}%')
print(f'MOIC: {metrics.get("MOIC", "N/A")}x')
exit_value = metrics.get("exit_equity_value", "N/A")
if exit_value != "N/A":
    print(f"Exit Value: €{exit_value:,.0f}")
else:
    print(f"Exit Value: {exit_value}")

# Check for errors
if "Error" in results:
    print(f'Error: {results["Error"]}')
else:
    print("Model completed successfully!")

    # Print some key metrics
    print("\n=== KEY METRICS ===")
    print(f"Entry Multiple: {assumptions.entry_ev_ebitda}x")
    print(f"Exit Multiple: {assumptions.exit_ev_ebitda}x")
    print(f"Revenue Base: €{assumptions.revenue0:,.0f}m")
    print(f"EBITDA Margin: {assumptions.ebitda_margin_start:.1%}")

    # Check debt service
    year_1_data = results.get("Year 1", {})
    if year_1_data:
        ltv_ratio = year_1_data.get("total_debt", 0) / year_1_data.get("ebitda", 1)
        interest_exp = year_1_data.get("interest_expense", 0)
        if interest_exp > 0:
            icr_ratio = year_1_data.get("ebitda", 0) / interest_exp
        else:
            icr_ratio = float("inf")

        print("\n=== YEAR 1 COVENANTS ===")
        print(
            f"LTV Ratio: {ltv_ratio:.1f}x "
            f"(Covenant: {assumptions.leverage_hurdle}x)"
        )
        print(f"ICR Ratio: {icr_ratio:.1f}x " f"(Covenant: {assumptions.icr_hurdle}x)")

        if ltv_ratio > (assumptions.leverage_hurdle or 0):
            print(f"⚠️  LTV BREACH: {ltv_ratio:.1f}x > {assumptions.leverage_hurdle}x")
        else:
            print(f"✅ LTV OK: {ltv_ratio:.1f}x ≤ {assumptions.leverage_hurdle}x")

        if icr_ratio < (assumptions.icr_hurdle or 0):
            print(f"⚠️  ICR BREACH: {icr_ratio:.1f}x < {assumptions.icr_hurdle}x")
        else:
            print(f"✅ ICR OK: {icr_ratio:.1f}x ≥ {assumptions.icr_hurdle}x")

# Run base case
print("Running base case with current assumptions...")
results, metrics = run_enhanced_base_case(assumptions)

print(f'IRR: {metrics.get("IRR", "N/A")}%')
print(f'MOIC: {metrics.get("MOIC", "N/A")}x')
exit_value = metrics.get("exit_equity_value", "N/A")
if exit_value != "N/A":
    print(f"Exit Value: ${exit_value:,.0f}")
else:
    print(f"Exit Value: {exit_value}")

# Check for errors
if "Error" in results:
    print(f'Error: {results["Error"]}')
else:
    print("Model completed successfully!")

    # Print some key metrics
    print("\n=== KEY METRICS ===")
    # Calculate derived values
    ebitda0 = assumptions.revenue0 * assumptions.ebitda_margin_start
    enterprise_value = assumptions.entry_ev_ebitda * ebitda0
    total_debt = enterprise_value * assumptions.debt_pct_of_ev
    equity_investment = enterprise_value - total_debt

    print(f"Initial Equity Investment: " f"€{equity_investment:,.0f}m")
    print(f"Total Debt: €{total_debt:,.0f}m")
    print(f"Enterprise Value: " f"€{enterprise_value:,.0f}m")
    print(f"Exit Multiple: {assumptions.exit_ev_ebitda}x")

    # Check debt service
    year_1_data = results.get("Year 1", {})
    if year_1_data:
        ltv_ratio = year_1_data.get("total_debt", 0) / year_1_data.get("ebitda", 1)
        interest_exp = year_1_data.get("interest_expense", 0)
        if interest_exp > 0:
            icr_ratio = year_1_data.get("ebitda", 0) / interest_exp
        else:
            icr_ratio = float("inf")
        print("\n=== YEAR 1 COVENANTS ===")
        print(
            f"LTV Ratio: {ltv_ratio:.1f}x "
            f"(Covenant: {assumptions.leverage_hurdle}x)"
        )
        print(f"ICR Ratio: {icr_ratio:.1f}x " f"(Covenant: {assumptions.icr_hurdle}x)")

        if ltv_ratio > (assumptions.leverage_hurdle or 0):
            print(f"⚠️  LTV BREACH: {ltv_ratio:.1f}x > {assumptions.leverage_hurdle}x")
        else:
            print(f"✅ LTV OK: {ltv_ratio:.1f}x ≤ {assumptions.leverage_hurdle}x")

        if icr_ratio < (assumptions.icr_hurdle or 0):
            print(f"⚠️  ICR BREACH: {icr_ratio:.1f}x < {assumptions.icr_hurdle}x")
        else:
            print(f"✅ ICR OK: {icr_ratio:.1f}x ≥ {assumptions.icr_hurdle}x")
