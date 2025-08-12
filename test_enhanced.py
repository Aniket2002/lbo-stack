#!/usr/bin/env python3
"""
Test script for the enhanced LBO model
This demonstrates the "buy-side serious" improvements
"""

from src.modules.orchestrator_advanced import main as run_enhanced_analysis

if __name__ == "__main__":
    print("=" * 60)
    print("ENHANCED LBO MODEL - PE-GRADE ANALYSIS")
    print("=" * 60)
    print()
    print("Key Improvements from Feedback:")
    print("✓ Realistic 65% leverage (vs 50% before)")
    print("✓ IFRS-16 lease liability modeling")
    print("✓ Covenant tracking (ICR, LTV, FCF coverage)")
    print("✓ 85% cash sweep with minimum cash buffer")
    print("✓ Maintenance vs growth CapEx separation")
    print("✓ Days-based working capital (vs % of revenue)")
    print("✓ Entry fees and transaction costs")
    print("✓ 3x3 sensitivity grid")
    print("✓ Monte Carlo analysis (500 scenarios)")
    print("✓ Enhanced PDF report with charts")
    print()
    print("Running analysis...")
    print("-" * 40)

    try:
        run_enhanced_analysis()
    except Exception as e:
        print(f"Error running analysis: {e}")
        print("Make sure you have the required data files in the data/ directory")
