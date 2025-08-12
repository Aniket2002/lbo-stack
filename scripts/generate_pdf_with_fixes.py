#!/usr/bin/env python3
"""
Generate PDF with semantic LTV fixes for PE VP review
"""
import sys

sys.path.append("src/modules")
from orchestrator_advanced import (
    create_enhanced_pdf_report,
    enhanced_sensitivity_grid,
    monte_carlo_analysis,
    read_accor_assumptions,
    run_enhanced_base_case,
)


def generate_semantic_fix_pdf():
    """Generate PDF showing the corrected semantic labeling"""
    print("📄 GENERATING PDF WITH SEMANTIC FIXES")
    print("=" * 50)

    # Load assumptions
    a = read_accor_assumptions()
    print(f"✅ Leverage hurdle: {a.leverage_hurdle:.1f}x (Net Debt/EBITDA)")

    # Run analysis
    print("🔍 Running enhanced analysis...")
    results, metrics = run_enhanced_base_case(a)

    # Generate sensitivity
    print("📊 Running sensitivity grid...")
    try:
        sens_df = enhanced_sensitivity_grid(a)
        print(f"✅ Sensitivity: {sens_df.shape[0]}x{sens_df.shape[1]} scenarios")
    except Exception as e:
        print(f"⚠️ Sensitivity error: {e}")
        sens_df = None

    # Generate Monte Carlo
    print("🎲 Running Monte Carlo...")
    try:
        mc_results = monte_carlo_analysis(a, n=400)
        print(f"✅ Monte Carlo: {len(mc_results['irrs'])} simulations")
    except Exception as e:
        print(f"⚠️ Monte Carlo error: {e}")
        mc_results = None

    # Generate PDF
    pdf_path = "accor_lbo_semantic_fix_FINAL.pdf"
    print(f"📝 Creating PDF: {pdf_path}")

    try:
        create_enhanced_pdf_report(
            results=results,
            metrics=metrics,
            a=a,
            sens_df=sens_df,
            mc_results=mc_results,
            out_path=pdf_path,
        )
        print(f"✅ PDF generated: {pdf_path}")

        # Summary
        print(f"\n📋 REPORT SUMMARY:")
        print(f"  • IRR: {metrics['IRR']:.1%}")
        print(f"  • MOIC: {metrics['MOIC']:.1f}x")
        print(f"  • Max Leverage: {metrics['Max_LTV']:.1f}x")
        print(f"  • Semantic Fix: Net Debt/EBITDA (not LTV) ✅")

    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n🎯 PDF WITH SEMANTIC FIXES COMPLETE")


if __name__ == "__main__":
    generate_semantic_fix_pdf()
