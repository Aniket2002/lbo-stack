#!/usr/bin/env python3
"""
Comparison: Basic vs Enhanced LBO Model
Shows the impact of PE-grade improvements
"""


def compare_models():
    print("=" * 70)
    print("LBO MODEL COMPARISON: BASIC vs ENHANCED (PE-GRADE)")
    print("=" * 70)

    comparison_data = [
        ("FEATURE", "BASIC MODEL", "ENHANCED MODEL", "IMPACT"),
        ("-" * 20, "-" * 25, "-" * 25, "-" * 15),
        ("Leverage", "50% (conservative)", "65% (realistic)", "+200-400bps IRR"),
        ("Working Capital", "% of revenue", "Days outstanding", "More accurate"),
        ("CapEx", "Single % rate", "Maintenance + Growth", "Realistic modeling"),
        ("D&A", "% of EBITDA", "% of revenue", "Better correlation"),
        ("Lease Treatment", "Ignored", "IFRS-16 in debt", "Covenant impact"),
        ("Cash Management", "No sweep", "85% sweep + min cash", "Faster delever"),
        ("Covenants", "Basic ICR", "ICR + LTV + FCF", "Comprehensive"),
        ("Sensitivity", "None", "3x3 grid + MC", "Risk assessment"),
        ("Transaction Costs", "Exit only", "Entry + Exit fees", "Realistic returns"),
        ("Debt Structure", "Simple", "Senior + Mezz + RCF", "Market standard"),
        ("", "", "", ""),
        ("Expected IRR", "~19% (conservative)", "22-25% (realistic)", "+300-600bps"),
        ("Covenant Risk", "Unknown", "Tracked/quantified", "Transparent"),
        ("Market Credibility", "Academic", "PE-ready", "Professional"),
    ]

    for row in comparison_data:
        print(f"{row[0]:<20} {row[1]:<25} {row[2]:<25} {row[3]:<15}")

    print("\n" + "=" * 70)
    print("KEY FIXES ADDRESSING PE FEEDBACK:")
    print("=" * 70)
    fixes = [
        "🔧 LEVERAGE: 50% → 65% (industry realistic)",
        "🔧 IFRS-16: Added 3.2x EBITDA lease liability",
        "🔧 CASH SWEEP: 85% with €150m minimum buffer",
        "🔧 COVENANTS: ICR ≥2.25x, LTV ≤6.5x, FCF coverage",
        "🔧 WORKING CAPITAL: Days-based (15d AR, 30d AP, 20d deferred)",
        "🔧 CAPEX: 2.5% maintenance + 1.5% growth",
        "🔧 FEES: 2% entry + 1% exit transaction costs",
        "🔧 SENSITIVITY: 3x3 grid + 500-scenario Monte Carlo",
        "🔧 REPORTING: Enhanced PDF with covenant tracking",
    ]

    for fix in fixes:
        print(fix)

    print("\n" + "=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print("1. Run test_enhanced.py to see the improved model")
    print("2. Review accor_lbo_enhanced.pdf for professional output")
    print("3. Calibrate assumptions using Accor's actual financials")
    print("4. Add seasonality/quarterly modeling if needed")
    print("5. Test stressed scenarios (recession, rate hikes)")


if __name__ == "__main__":
    compare_models()
