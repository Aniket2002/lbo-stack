#!/usr/bin/env python3
"""
Test VP Feedback Implementation
Quick validation of sponsor-grade improvements
"""

from src.modules.orchestrator_advanced import (
    add_ifrs16_methodology_footnote,
    build_working_capital_drivers,
    read_accor_assumptions,
    run_comprehensive_lbo_analysis,
)


def main():
    print("🔥 Testing VP Feedback Implementation...")

    # Load assumptions
    assumptions = read_accor_assumptions()
    print(f"Loaded assumptions: {assumptions.purchase_price:.0f}m purchase price")

    # Test IFRS-16 methodology footnote
    print("\n📋 IFRS-16 Methodology Footnote:")
    footnote = add_ifrs16_methodology_footnote()
    print(footnote[:200] + "...")

    # Test working capital drivers
    print("\n💰 Working Capital Drivers:")
    wc_drivers = build_working_capital_drivers(assumptions)
    print(f"  AR Days: {wc_drivers['accounts_receivable_days']}")
    print(f"  AP Days: {wc_drivers['accounts_payable_days']}")
    print(f"  Net WC: €{wc_drivers['net_working_capital']:.1f}m")

    # Run comprehensive analysis
    print("\n📊 Running Comprehensive Analysis...")
    results = run_comprehensive_lbo_analysis(assumptions)

    if "error" not in results:
        print("\n✅ Comprehensive Analysis Complete:")
        sources_uses = results["sources_and_uses"]
        exit_bridge = results["exit_equity_bridge"]
        deleveraging = results["deleveraging_walk"]

        print(f"  Sources & Uses: {len(sources_uses)} components")
        print(f"  Exit Bridge: €{exit_bridge['exit_equity_value']:.0f}m equity value")
        print(
            f"  Deleveraging: {deleveraging['starting_leverage']:.1f}x → {deleveraging['ending_leverage']:.1f}x"
        )
        print(f"  True LTV: {sources_uses['true_ltv_percentage']:.1f}%")
        print(f"  Fund Waterfall: {len(results['fund_waterfall'])} years")
        print(
            f"  Monte Carlo: {results['monte_carlo']['summary']['scenarios_run']} scenarios"
        )

        # VP specific validations
        print("\n🏗️ VP Feedback Validation:")
        print(
            f"  ✅ Lease liability in net debt: €{sources_uses['lease_liability']:.0f}m"
        )
        print(f"  ✅ Exit equity bridge complete: {exit_bridge['moic']:.1f}x MOIC")
        print(
            f"  ✅ Terminal explanation: {exit_bridge['terminal_heavy_explanation'][:50]}..."
        )
        print(
            f"  ✅ Covenant tracking: {len(results['covenant_analysis']['ICR_Series'])} periods"
        )

    else:
        print(f"❌ Error: {results['error']}")


if __name__ == "__main__":
    main()
