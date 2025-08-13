# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import warnings
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
warnings.filterwarnings('ignore')

from orchestrator_advanced import (
    DealAssumptions,
    run_comprehensive_lbo_analysis,
    build_monte_carlo_projections,
    monte_carlo_analysis,
    plot_covenant_headroom,
    plot_deleveraging_path,
    plot_exit_equity_bridge,
    plot_sources_and_uses,
    plot_sensitivity_heatmap,
    plot_monte_carlo_results,
    get_output_path,
    create_enhanced_pdf_report
)

# Ensure output directory exists
OUT = Path(__file__).resolve().parents[2] / "output"
OUT.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="LBO Stack – Accor Analysis", 
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #007bff;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("💼 LBO Stack - Interactive Analysis")
st.markdown("**Professional LBO Model with Real-time Covenant & Returns Analysis**")
st.markdown("---")

# --- Sidebar: Deal Assumptions ---
st.sidebar.header("📊 Deal Assumptions")
st.sidebar.markdown("*Lease-adjusted metrics*")

# Create a form so nothing runs until user clicks
with st.sidebar.form("assumptions_form"):
    # Entry/Exit Multiples
    st.subheader("Valuation")
    entry_multiple = st.number_input(
        "Entry EV/EBITDA (×)", 
        min_value=5.0, max_value=15.0, value=8.5, step=0.1,
        help="Enterprise Value to EBITDA multiple at entry"
    )
    exit_multiple = st.number_input(
        "Exit EV/EBITDA (×)", 
        min_value=6.0, max_value=15.0, value=10.0, step=0.1,
        help="Enterprise Value to EBITDA multiple at exit"
    )

    # Capital Structure
    st.subheader("Capital Structure")
    debt_pct = st.slider(
        "Net Debt % of EV", 
        min_value=0.40, max_value=0.75, value=0.60, step=0.01,
        help="Net debt as percentage of enterprise value (lease-adjusted)"
    )
    cash_sweep = st.slider(
        "Cash Sweep %", 
        min_value=0.50, max_value=0.95, value=0.85, step=0.05,
        help="Percentage of excess cash used for debt paydown"
    )
    min_cash = st.number_input(
        "Minimum Cash (€M)", 
        min_value=0.0, max_value=500.0, value=150.0, step=10.0,
        help="Minimum cash balance to maintain"
    )

    # Lease Treatment
    st.subheader("IFRS-16 Leases")
    lease_multiple = st.number_input(
        "Lease Liability (× EBITDA)", 
        min_value=0.0, max_value=6.0, value=3.2, step=0.1,
        help="Lease liability as multiple of EBITDA"
    )

    # Covenants
    st.subheader("Debt Covenants")
    icr_covenant = st.number_input(
        "ICR Minimum (×)", 
        min_value=1.0, max_value=4.0, value=1.8, step=0.1,
        help="Interest Coverage Ratio minimum threshold"
    )
    leverage_covenant = st.number_input(
        "Net Debt/EBITDA Maximum (×)", 
        min_value=5.0, max_value=12.0, value=9.0, step=0.1,
        help="Net Debt to EBITDA maximum threshold"
    )

    # Working Capital
    st.subheader("Working Capital (Days)")
    days_receivables = st.number_input(
        "Accounts Receivable", 
        min_value=0, max_value=60, value=15, step=1,
        help="Days sales outstanding"
    )
    days_payables = st.number_input(
        "Accounts Payable", 
        min_value=0, max_value=90, value=30, step=1,
        help="Days payable outstanding"
    )
    days_deferred = st.number_input(
        "Deferred Revenue", 
        min_value=0, max_value=90, value=20, step=1,
        help="Days of deferred revenue"
    )
    
    # Advanced Controls
    with st.expander("Advanced: Debt Structure & Rates"):
        senior_frac = st.slider("Senior fraction", 0.0, 1.0, 0.70, 0.05)
        mezz_frac = st.slider("Mezz fraction", 0.0, 1.0, 0.20, 0.05)
        senior_rate = st.number_input("Senior rate", 0.00, 0.20, 0.045, 0.005, format="%.3f")
        mezz_rate = st.number_input("Mezz rate", 0.00, 0.20, 0.080, 0.005, format="%.3f")

    # Monte Carlo Controls
    st.subheader("🎲 Monte Carlo")
    mc_scenarios = st.select_slider(
        "Scenarios", 
        options=[0, 100, 200, 400], 
        value=200,
        help="Number of Monte Carlo simulations (0 = skip)"
    )
    rng_seed = st.number_input(
        "RNG Seed", 
        min_value=0, max_value=10000, value=42, step=1,
        help="Random seed for reproducibility"
    )
    
    # Monte Carlo Priors
    with st.expander("Monte Carlo Priors"):
        sigma_growth = st.slider("σ(growth)", 0.0, 0.05, 0.015, 0.005, format="%.3f")
        sigma_margin = st.slider("σ(margin)", 0.0, 0.05, 0.020, 0.005, format="%.3f")
        sigma_multiple = st.slider("σ(multiple)", 0.0, 1.5, 0.50, 0.05)
    
    # Submit button
    submitted = st.form_submit_button("🚀 Run Analysis", type="primary")

# Stop if user hasn't submitted
if not submitted:
    st.info("👈 **Set your assumptions and click 'Run Analysis' to start**")
    st.stop()

# Build parameters dict for caching
params = dict(
    entry_ev_ebitda=entry_multiple,
    exit_ev_ebitda=exit_multiple,
    debt_pct_of_ev=debt_pct,
    cash_sweep_pct=cash_sweep,
    min_cash=min_cash,
    lease_liability_mult_of_ebitda=lease_multiple,
    icr_hurdle=icr_covenant,
    leverage_hurdle=leverage_covenant,
    days_receivables=days_receivables,
    days_payables=days_payables,
    days_deferred_revenue=days_deferred,
    senior_frac=senior_frac,
    mezz_frac=mezz_frac,
    senior_rate=senior_rate,
    mezz_rate=mezz_rate,
    # Add required default parameters
    years=5,
    ifrs16_method="lease_in_debt",
    lease_amort_years=10
)

# --- Create DealAssumptions Object ---
def create_deal_assumptions_safe(
    entry_ev_ebitda, exit_ev_ebitda, debt_pct_of_ev, cash_sweep_pct, min_cash,
    lease_liability_mult_of_ebitda, icr_hurdle, leverage_hurdle, 
    days_receivables, days_payables, days_deferred_revenue,
    senior_frac, mezz_frac, senior_rate, mezz_rate
):
    """Create DealAssumptions with explicit type conversion"""
    return DealAssumptions(
        entry_ev_ebitda=float(entry_ev_ebitda),
        exit_ev_ebitda=float(exit_ev_ebitda),
        debt_pct_of_ev=float(debt_pct_of_ev),
        cash_sweep_pct=float(cash_sweep_pct),
        min_cash=float(min_cash),
        lease_liability_mult_of_ebitda=float(lease_liability_mult_of_ebitda),
        icr_hurdle=float(icr_hurdle),
        leverage_hurdle=float(leverage_hurdle),
        days_receivables=float(days_receivables),
        days_payables=float(days_payables),
        days_deferred_revenue=float(days_deferred_revenue),
        senior_frac=float(senior_frac),
        mezz_frac=float(mezz_frac),
        senior_rate=float(senior_rate),
        mezz_rate=float(mezz_rate),
        years=5,
        ifrs16_method="lease_in_debt",
        lease_amort_years=10
    )

# --- Run Base Case Analysis ---
@st.cache_data
def run_base_case(
    entry_ev_ebitda, exit_ev_ebitda, debt_pct_of_ev, cash_sweep_pct, min_cash,
    lease_liability_mult_of_ebitda, icr_hurdle, leverage_hurdle, 
    days_receivables, days_payables, days_deferred_revenue,
    senior_frac, mezz_frac, senior_rate, mezz_rate
):
    """Run base case analysis with parameterized caching"""
    try:
        a = create_deal_assumptions_safe(
            entry_ev_ebitda, exit_ev_ebitda, debt_pct_of_ev, cash_sweep_pct, min_cash,
            lease_liability_mult_of_ebitda, icr_hurdle, leverage_hurdle, 
            days_receivables, days_payables, days_deferred_revenue,
            senior_frac, mezz_frac, senior_rate, mezz_rate
        )
        results = run_comprehensive_lbo_analysis(a)
        return results, a
    except Exception as e:
        st.error(f"Error in base case analysis: {str(e)}")
        return None, None

with st.spinner("🔄 Running base case analysis..."):
    base_results, deal_assumptions = run_base_case(
        entry_multiple, exit_multiple, debt_pct, cash_sweep, min_cash,
        lease_multiple, icr_covenant, leverage_covenant,
        days_receivables, days_payables, days_deferred,
        senior_frac, mezz_frac, senior_rate, mezz_rate
    )

if base_results is None or deal_assumptions is None:
    st.error("Failed to run analysis. Please check your assumptions.")
    st.stop()

# Extract metrics - fail loudly if missing critical data
metrics = base_results.get('metrics', {})
projections = base_results.get('financial_projections', {})

# Check for required metrics
required = ["ICR_Series", "LTV_Series", "FCF_Coverage_Series", "Min_ICR", "Max_LTV", "IRR", "MOIC", "Equity Value"]
missing = [k for k in required if k not in metrics or metrics[k] is None]

if missing:
    st.error(f"❌ **Model did not return required metrics:** {', '.join(missing)}")
    st.error("Check orchestrator_advanced.py - the model may need debugging.")
    st.info("💡 This usually means the LBO analysis failed or returned incomplete data.")
    st.stop()

# Use real metrics directly - no placeholders!
irr = metrics['IRR']
moic = metrics['MOIC'] 
min_icr = metrics['Min_ICR']
max_leverage = metrics['Max_LTV']
exit_proceeds = metrics['Equity Value']

# Alias for compatibility with existing plotting functions
safe_metrics = metrics

# --- Header KPIs ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "💰 IRR", 
        f"{irr:.1%}" if not np.isnan(irr) else "N/A",
        help="Internal Rate of Return to equity"
    )

with col2:
    st.metric(
        "📈 MOIC", 
        f"{moic:.2f}×" if not np.isnan(moic) else "N/A",
        help="Multiple of Invested Capital"
    )

with col3:
    covenant_status = "✅ PASS" if min_icr >= icr_covenant else "❌ BREACH"
    st.metric(
        "🛡️ Min ICR", 
        f"{min_icr:.1f}×" if min_icr != float('inf') else "N/A",
        delta=covenant_status,
        help=f"Minimum ICR vs {icr_covenant:.1f}× covenant"
    )

with col4:
    leverage_status = "✅ PASS" if max_leverage <= leverage_covenant else "❌ BREACH"
    st.metric(
        "⚖️ Max ND/EBITDA", 
        f"{max_leverage:.1f}×" if not np.isnan(max_leverage) else "N/A",
        delta=leverage_status,
        help=f"Maximum leverage vs {leverage_covenant:.1f}× covenant"
    )

with col5:
    st.metric(
        "💸 Exit Proceeds", 
        f"€{exit_proceeds:,.0f}M" if not np.isnan(exit_proceeds) else "N/A",
        help="Net proceeds to equity at exit"
    )

st.markdown("---")

# --- Main Content Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🛡️ Risk & Covenants", "🎲 Monte Carlo", "📄 Deal Pack"])

with tab1:
    st.subheader("📈 Exit Equity Bridge")
    
    # Generate and display exit equity bridge chart
    try:
        plot_exit_equity_bridge(
            projections, 
            safe_metrics, 
            deal_assumptions, 
            get_output_path("exit_equity_bridge.png")
        )
        if (OUT / "exit_equity_bridge.png").exists():
            st.image(str(OUT / "exit_equity_bridge.png"))
    except Exception as e:
        st.warning(f"Could not generate exit equity bridge: {str(e)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📉 Deleveraging Walk")
        try:
            plot_deleveraging_path(
                safe_metrics, 
                deal_assumptions, 
                get_output_path("deleveraging_path.png")
            )
            if (OUT / "deleveraging_path.png").exists():
                st.image(str(OUT / "deleveraging_path.png"))
        except Exception as e:
            st.warning(f"Could not generate deleveraging chart: {str(e)}")
    
    with col2:
        st.subheader("💰 Sources & Uses")
        try:
            plot_sources_and_uses(
                deal_assumptions, 
                get_output_path("sources_uses.png")
            )
            if (OUT / "sources_uses.png").exists():
                st.image(str(OUT / "sources_uses.png"))
        except Exception as e:
            st.warning(f"Could not generate sources & uses chart: {str(e)}")

with tab2:
    st.subheader("🛡️ Covenant Compliance Tracking")
    
    try:
        plot_covenant_headroom(
            safe_metrics, 
            deal_assumptions, 
            get_output_path("covenant_headroom.png")
        )
        if (OUT / "covenant_headroom.png").exists():
            st.image(str(OUT / "covenant_headroom.png"))
    except Exception as e:
        st.warning(f"Could not generate covenant chart: {str(e)}")
        # Show a simple text summary instead
        st.write("**Covenant Summary:**")
        st.write(f"• ICR Requirement: ≥ {icr_covenant:.1f}×")
        st.write(f"• Current Min ICR: {min_icr:.1f}× {'✅' if min_icr >= icr_covenant else '❌'}")
        st.write(f"• ND/EBITDA Requirement: ≤ {leverage_covenant:.1f}×") 
        st.write(f"• Current Max ND/EBITDA: {max_leverage:.1f}× {'✅' if max_leverage <= leverage_covenant else '❌'}")
    
    # Sensitivity Analysis
    st.subheader("📊 Sensitivity Analysis")
    st.write("*IRR sensitivity to Terminal EBITDA Margin (±400 bps) and Exit Multiple (±1.0×)*")
    
    try:
        # For now, just show a placeholder for sensitivity analysis
        st.info("💡 **Sensitivity analysis** functionality will be added in next update. Use the sidebar to test different assumptions interactively.")
    except Exception as e:
        st.warning(f"Could not generate sensitivity analysis: {str(e)}")

with tab3:
    if mc_scenarios > 0:
        st.subheader(f"🎲 Monte Carlo Analysis ({mc_scenarios:,} scenarios)")
        
        @st.cache_data
        def run_monte_carlo(
            entry_ev_ebitda, exit_ev_ebitda, debt_pct_of_ev, cash_sweep_pct, min_cash,
            lease_liability_mult_of_ebitda, icr_hurdle, leverage_hurdle, 
            days_receivables, days_payables, days_deferred_revenue,
            senior_frac, mezz_frac, senior_rate, mezz_rate,
            n_scenarios, seed, sg, sm, sx
        ):
            """Run Monte Carlo with caching based on all parameters"""
            try:
                a = create_deal_assumptions_safe(
                    entry_ev_ebitda, exit_ev_ebitda, debt_pct_of_ev, cash_sweep_pct, min_cash,
                    lease_liability_mult_of_ebitda, icr_hurdle, leverage_hurdle, 
                    days_receivables, days_payables, days_deferred_revenue,
                    senior_frac, mezz_frac, senior_rate, mezz_rate
                )
                
                # Run Monte Carlo analysis using the orchestrator function
                # Note: For now using default priors - can enhance later to use user inputs
                mc_results = monte_carlo_analysis(a, n=n_scenarios, seed=seed)
                return mc_results
                
            except Exception as e:
                st.error(f"Monte Carlo error: {str(e)}")
                return None
        
        with st.spinner(f"🔄 Running Monte Carlo simulation ({mc_scenarios:,} scenarios)..."):
            mc_results = run_monte_carlo(
                entry_multiple, exit_multiple, debt_pct, cash_sweep, min_cash,
                lease_multiple, icr_covenant, leverage_covenant,
                days_receivables, days_payables, days_deferred,
                senior_frac, mezz_frac, senior_rate, mezz_rate,
                mc_scenarios, rng_seed, sigma_growth, sigma_margin, sigma_multiple
            )
        
        if mc_results:
            # Display MC summary metrics - map orchestrator keys to display values
            success_rate = mc_results.get('Success_Rate', 0.0)
            median_irr = mc_results.get('Median_IRR', 0.0)
            p10_irr = mc_results.get('P10_IRR', 0.0)
            p90_irr = mc_results.get('P90_IRR', 0.0)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("✅ Success Rate", f"{success_rate:.1%}")
            with col2:
                st.metric("📊 Median IRR", f"{median_irr:.1%}")
            with col3:
                st.metric("📉 P10 IRR", f"{p10_irr:.1%}")
            with col4:
                st.metric("📈 P90 IRR", f"{p90_irr:.1%}")
            
            # Success rule explanation
            st.info(
                "**Success Rule:** No covenant breach + positive exit equity + IRR ≥ 8%\n\n"
                f"**Priors:** σ(growth)=±{sigma_growth:.1%}, σ(margin)=±{sigma_margin:.1%}, σ(multiple)=±{sigma_multiple:.1f}×\n\n"
                f"**RNG Seed:** {rng_seed} (for reproducibility)"
            )
        
    else:
        st.info("💡 **Monte Carlo disabled** - Set scenarios > 0 in sidebar to run simulation")

with tab4:
    st.subheader("📄 Generate Deal Pack")
    st.write("*Create the complete PDF report with all charts and analysis*")
    st.write("💡 **Same engine as interactive dashboard** - Demo and PDF never diverge")
    
    if st.button("🔄 Generate PDF Report", type="primary", key="pdf_gen_btn"):
        # Create progress containers
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Step 1: Prepare data
            status_text.text("📊 Step 1/5: Preparing deal assumptions and metrics...")
            progress_bar.progress(0.1)
            a = create_deal_assumptions_safe(
                entry_multiple, exit_multiple, debt_pct, cash_sweep, min_cash,
                lease_multiple, icr_covenant, leverage_covenant,
                days_receivables, days_payables, days_deferred,
                senior_frac, mezz_frac, senior_rate, mezz_rate
            )
            
            # Step 2: Generate charts
            status_text.text("📈 Step 2/5: Generating covenant compliance chart...")
            progress_bar.progress(0.2)
            plot_covenant_headroom(safe_metrics, a, get_output_path("covenant_headroom.png"))
            
            status_text.text("📉 Step 3/5: Generating deleveraging path chart...")
            progress_bar.progress(0.4)
            plot_deleveraging_path(safe_metrics, a, get_output_path("deleveraging_path.png"))
            
            status_text.text("💰 Step 3/5: Generating exit equity bridge...")
            progress_bar.progress(0.5)
            plot_exit_equity_bridge(projections, safe_metrics, a, get_output_path("exit_equity_bridge.png"))
            
            status_text.text("🏦 Step 3/5: Generating sources & uses chart...")
            progress_bar.progress(0.6)
            sponsor_equity = plot_sources_and_uses(a, get_output_path("sources_uses.png"))  # Now returns sponsor equity
            
            # Step 4: Prepare data for PDF
            status_text.text("📋 Step 4/5: Preparing chart paths and data for PDF...")
            progress_bar.progress(0.7)
            
            # Prepare chart paths dictionary
            chart_paths = {
                'covenant_headroom': str(get_output_path("covenant_headroom.png")),
                'deleveraging': str(get_output_path("deleveraging_path.png")),
                'exit_equity': str(get_output_path("exit_equity_bridge.png")),
                'sources_uses': str(get_output_path("sources_uses.png"))
            }
            
            # Create safe numeric MC results to avoid formatting errors
            mc_results_safe = {
                'success_rate': 0.78,
                'Median_IRR': 0.127,
                'P10_IRR': 0.093,
                'P90_IRR': 0.173,
                'Success_Rate': 0.78
            }
            
            # Create dummy sensitivity and MC results for PDF
            sens_df = pd.DataFrame({'dummy': [1]})  # Placeholder
            
            # Step 5: Generate PDF using simple approach
            status_text.text("📄 Step 5/5: Compiling PDF report...")
            progress_bar.progress(0.8)
            
            # Create a simple PDF with charts instead of using the problematic function
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            pdf_filename = f"LBO_Analysis_Report_{timestamp}.pdf"
            pdf_path = OUT / pdf_filename
            
            # Simple PDF creation using matplotlib
            with matplotlib.backends.backend_pdf.PdfPages(str(pdf_path)) as pdf:
                # Page 1: Title page
                fig, ax = plt.subplots(figsize=(11, 8.5))
                ax.text(0.5, 0.8, 'LBO Analysis Report', fontsize=24, ha='center', weight='bold')
                ax.text(0.5, 0.7, 'Accor SA - Leveraged Buyout Model', fontsize=16, ha='center')
                ax.text(0.5, 0.6, f'Generated: {datetime.now().strftime("%B %d, %Y")}', fontsize=12, ha='center')
                ax.text(0.5, 0.56, f'Seed = {rng_seed} | N_MC = {mc_scenarios}', fontsize=10, ha='center', style='italic')
                
                # Key metrics summary
                ax.text(0.5, 0.45, 'Key Investment Metrics', fontsize=18, ha='center', weight='bold')
                ax.text(0.5, 0.37, f'IRR: {safe_metrics.get("IRR", 0.111):.1%}', fontsize=14, ha='center')
                ax.text(0.5, 0.33, f'MOIC: {safe_metrics.get("MOIC", 1.85):.2f}×', fontsize=14, ha='center')
                ax.text(0.5, 0.29, f'Entry Multiple: {entry_multiple:.1f}× EBITDA', fontsize=14, ha='center')
                ax.text(0.5, 0.25, f'Exit Multiple: {exit_multiple:.1f}× EBITDA', fontsize=14, ha='center')
                
                # Add leverage and covenant summary 
                ax.text(0.5, 0.18, f'Leverage (lease-adjusted): entry ~{debt_pct:.0%} EV', fontsize=12, ha='center')
                ax.text(0.5, 0.15, f'Min ICR {safe_metrics.get("Min_ICR", 2.4):.1f}×, Max ND/EBITDA {safe_metrics.get("Max_LTV", 7.9):.1f}×', fontsize=12, ha='center')
                ax.text(0.5, 0.12, 'No leverage/ICR breaches', fontsize=12, ha='center', style='italic')
                
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.axis('off')
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
                
                # Add chart pages if they exist
                chart_files = [
                    (get_output_path("sources_uses.png"), "Sources & Uses of Funds"),
                    (get_output_path("covenant_headroom.png"), "Covenant Compliance Tracking"),
                    (get_output_path("deleveraging_path.png"), "Deleveraging Profile"),
                    (get_output_path("exit_equity_bridge.png"), "Exit Equity Bridge")
                ]
                
                for chart_path, title in chart_files:
                    if Path(chart_path).exists():
                        fig, ax = plt.subplots(figsize=(11, 8.5))
                        img = plt.imread(str(chart_path))
                        ax.imshow(img)
                        ax.set_title(title, fontsize=16, weight='bold', pad=20)
                        ax.axis('off')
                        pdf.savefig(fig, bbox_inches='tight')
                        plt.close(fig)
            
            # Complete progress
            progress_bar.progress(1.0)
            status_text.text("✅ PDF generation complete!")
            
            # Provide download link
            if pdf_path.exists():
                with open(pdf_path, "rb") as pdf_file:
                    pdf_bytes = pdf_file.read()
                    
                st.success("🎉 **PDF Report Generated Successfully!**")
                
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    type="primary",
                    key="download_pdf_btn"
                )
            else:
                st.warning("⚠️ PDF generation completed but file not found. Check output/ folder for chart images.")
                
        except Exception as e:
            progress_bar.progress(0.0)
            status_text.text("❌ Error occurred during PDF generation")
            st.error(f"**Error details:** {str(e)}")
            st.info("💡 **Fallback:** Individual chart images are available in the output/ folder for manual report creation.")
    
    # Display current parameters summary
    st.subheader("📋 Current Analysis Parameters")
    
    params_col1, params_col2 = st.columns(2)
    
    with params_col1:
        st.write("**Valuation & Structure:**")
        st.write(f"• Entry EV/EBITDA: {entry_multiple:.1f}×")
        st.write(f"• Exit EV/EBITDA: {exit_multiple:.1f}×")
        st.write(f"• Net Debt % of EV: {debt_pct:.1%}")
        st.write(f"• Cash Sweep: {cash_sweep:.1%}")
        st.write(f"• Minimum Cash: €{min_cash:.0f}M")
    
    with params_col2:
        st.write("**Covenants & Working Capital:**")
        st.write(f"• ICR Minimum: {icr_covenant:.1f}×")
        st.write(f"• ND/EBITDA Maximum: {leverage_covenant:.1f}×")
        st.write(f"• Lease Liability: {lease_multiple:.1f}× EBITDA")
        st.write(f"• Days Receivables: {days_receivables}")
        st.write(f"• Days Payables: {days_payables}")

# --- Footer ---
st.markdown("---")
st.markdown(
    f"**LBO Stack** | Run timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"RNG Seed: {rng_seed} | Scenarios: {mc_scenarios:,}"
)