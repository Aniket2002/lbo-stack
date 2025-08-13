# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import warnings
warnings.filterwarnings('ignore')

# Add src/modules to path
sys.path.append(str(Path(__file__).resolve().parent / "src" / "modules"))

from orchestrator_advanced import (
    run_lbo_analysis,
    monte_carlo_analysis,
    sensitivity_analysis,
    create_enhanced_pdf_report,
    plot_covenant_headroom,
    plot_deleveraging_path,
    plot_exit_equity_bridge,
    plot_sources_uses,
    plot_sensitivity_heatmap,
    plot_monte_carlo_distribution,
    get_output_path
)

# Ensure output directory exists
OUT = Path(__file__).resolve().parent / "output"
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

# Entry/Exit Multiples
st.sidebar.subheader("Valuation")
entry_multiple = st.sidebar.number_input(
    "Entry EV/EBITDA (×)", 
    min_value=5.0, max_value=15.0, value=8.5, step=0.1,
    help="Enterprise Value to EBITDA multiple at entry"
)
exit_multiple = st.sidebar.number_input(
    "Exit EV/EBITDA (×)", 
    min_value=6.0, max_value=15.0, value=9.0, step=0.1,
    help="Enterprise Value to EBITDA multiple at exit"
)

# Capital Structure
st.sidebar.subheader("Capital Structure")
debt_pct = st.sidebar.slider(
    "Net Debt % of EV", 
    min_value=0.40, max_value=0.75, value=0.60, step=0.01,
    help="Net debt as percentage of enterprise value (lease-adjusted)"
)
cash_sweep = st.sidebar.slider(
    "Cash Sweep %", 
    min_value=0.50, max_value=0.95, value=0.85, step=0.05,
    help="Percentage of excess cash used for debt paydown"
)
min_cash = st.sidebar.number_input(
    "Minimum Cash (€M)", 
    min_value=0.0, max_value=500.0, value=150.0, step=10.0,
    help="Minimum cash balance to maintain"
)

# Lease Treatment
st.sidebar.subheader("IFRS-16 Leases")
lease_multiple = st.sidebar.number_input(
    "Lease Liability (× EBITDA)", 
    min_value=0.0, max_value=6.0, value=3.2, step=0.1,
    help="Lease liability as multiple of EBITDA"
)

# Covenants
st.sidebar.subheader("Debt Covenants")
icr_covenant = st.sidebar.number_input(
    "ICR Minimum (×)", 
    min_value=1.0, max_value=4.0, value=2.2, step=0.1,
    help="Interest Coverage Ratio minimum threshold"
)
leverage_covenant = st.sidebar.number_input(
    "Net Debt/EBITDA Maximum (×)", 
    min_value=5.0, max_value=12.0, value=9.0, step=0.1,
    help="Net Debt to EBITDA maximum threshold"
)

# Working Capital
st.sidebar.subheader("Working Capital (Days)")
days_receivables = st.sidebar.number_input(
    "Accounts Receivable", 
    min_value=0, max_value=60, value=15, step=1,
    help="Days sales outstanding"
)
days_payables = st.sidebar.number_input(
    "Accounts Payable", 
    min_value=0, max_value=90, value=30, step=1,
    help="Days payable outstanding"
)
days_deferred = st.sidebar.number_input(
    "Deferred Revenue", 
    min_value=0, max_value=90, value=20, step=1,
    help="Days of deferred revenue"
)

# Monte Carlo Controls
st.sidebar.subheader("🎲 Monte Carlo")
mc_scenarios = st.sidebar.select_slider(
    "Scenarios", 
    options=[0, 100, 200, 400], 
    value=200,
    help="Number of Monte Carlo simulations (0 = skip)"
)
rng_seed = st.sidebar.number_input(
    "RNG Seed", 
    min_value=0, max_value=10000, value=42, step=1,
    help="Random seed for reproducibility"
)

# --- Build Assumptions Dictionary ---
assumptions = {
    'entry_ev_ebitda_multiple': entry_multiple,
    'exit_ev_ebitda_multiple': exit_multiple,
    'debt_percentage_of_ev': debt_pct,
    'cash_sweep_percentage': cash_sweep,
    'minimum_cash_balance': min_cash,
    'lease_liability_multiple': lease_multiple,
    'icr_covenant': icr_covenant,
    'leverage_covenant': leverage_covenant,
    'days_receivables': days_receivables,
    'days_payables': days_payables,
    'days_deferred_revenue': days_deferred,
    'monte_carlo_scenarios': mc_scenarios,
    'random_seed': rng_seed
}

# --- Run Base Case Analysis ---
@st.cache_data
def run_base_case(assumptions_dict):
    """Run base case analysis with caching"""
    try:
        results = run_lbo_analysis(assumptions_dict)
        return results
    except Exception as e:
        st.error(f"Error in base case analysis: {str(e)}")
        return None

with st.spinner("🔄 Running base case analysis..."):
    base_results = run_base_case(assumptions)

if base_results is None:
    st.error("Failed to run analysis. Please check your assumptions.")
    st.stop()

# Extract key metrics
metrics = base_results.get('metrics', {})
irr = metrics.get('equity_irr', 0.0)
moic = metrics.get('equity_moic', 0.0)
min_icr = metrics.get('minimum_icr', float('inf'))
max_leverage = metrics.get('maximum_net_debt_ebitda', 0.0)

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
    exit_proceeds = metrics.get('exit_proceeds', 0.0)
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
            base_results.get('projections', {}), 
            assumptions, 
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
                base_results.get('projections', {}), 
                get_output_path("deleveraging_path.png")
            )
            if (OUT / "deleveraging_path.png").exists():
                st.image(str(OUT / "deleveraging_path.png"))
        except Exception as e:
            st.warning(f"Could not generate deleveraging chart: {str(e)}")
    
    with col2:
        st.subheader("💰 Sources & Uses")
        try:
            plot_sources_uses(
                base_results.get('projections', {}), 
                assumptions, 
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
            base_results.get('projections', {}), 
            assumptions, 
            get_output_path("covenant_headroom.png")
        )
        if (OUT / "covenant_headroom.png").exists():
            st.image(str(OUT / "covenant_headroom.png"))
    except Exception as e:
        st.warning(f"Could not generate covenant chart: {str(e)}")
    
    # Sensitivity Analysis
    st.subheader("📊 Sensitivity Analysis")
    st.write("*IRR sensitivity to Terminal EBITDA Margin (±400 bps) and Exit Multiple (±1.0×)*")
    
    try:
        sens_results = sensitivity_analysis(assumptions)
        plot_sensitivity_heatmap(
            sens_results, 
            get_output_path("sensitivity_heatmap.png")
        )
        if (OUT / "sensitivity_heatmap.png").exists():
            st.image(str(OUT / "sensitivity_heatmap.png"))
    except Exception as e:
        st.warning(f"Could not generate sensitivity analysis: {str(e)}")

with tab3:
    if mc_scenarios > 0:
        st.subheader(f"🎲 Monte Carlo Analysis ({mc_scenarios:,} scenarios)")
        
        @st.cache_data
        def run_monte_carlo(assumptions_dict, n_scenarios, seed):
            """Run Monte Carlo with caching"""
            try:
                mc_assumptions = assumptions_dict.copy()
                mc_assumptions['monte_carlo_scenarios'] = n_scenarios
                mc_assumptions['random_seed'] = seed
                return monte_carlo_analysis(mc_assumptions)
            except Exception as e:
                st.error(f"Monte Carlo error: {str(e)}")
                return None
        
        with st.spinner(f"🔄 Running Monte Carlo simulation ({mc_scenarios:,} scenarios)..."):
            mc_results = run_monte_carlo(assumptions, mc_scenarios, rng_seed)
        
        if mc_results:
            # Display MC summary metrics
            success_rate = mc_results.get('success_rate', 0.0)
            median_irr = mc_results.get('median_irr', 0.0)
            p10_irr = mc_results.get('p10_irr', 0.0)
            p90_irr = mc_results.get('p90_irr', 0.0)
            
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
                f"**Priors:** σ(growth)=±150 bps, σ(margin)=±200 bps, σ(multiple)=±0.5×\n\n"
                f"**RNG Seed:** {rng_seed} (for reproducibility)"
            )
            
            # Generate and display MC chart
            try:
                plot_monte_carlo_distribution(
                    mc_results, 
                    get_output_path("monte_carlo.png")
                )
                if (OUT / "monte_carlo.png").exists():
                    st.image(str(OUT / "monte_carlo.png"))
            except Exception as e:
                st.warning(f"Could not generate Monte Carlo chart: {str(e)}")
        
    else:
        st.info("💡 **Monte Carlo disabled** - Set scenarios > 0 in sidebar to run simulation")

with tab4:
    st.subheader("📄 Generate Deal Pack")
    st.write("*Create the complete PDF report with all charts and analysis*")
    
    if st.button("🔄 Generate PDF Report", type="primary"):
        with st.spinner("📄 Generating comprehensive PDF report..."):
            try:
                # Run full analysis to ensure all charts are generated
                sens_results = sensitivity_analysis(assumptions) if 'sens_results' not in locals() else sens_results
                mc_results_full = monte_carlo_analysis(assumptions) if mc_scenarios > 0 else None
                
                # Generate all charts
                plot_covenant_headroom(base_results.get('projections', {}), assumptions, get_output_path("covenant_headroom.png"))
                plot_deleveraging_path(base_results.get('projections', {}), get_output_path("deleveraging_path.png"))
                plot_exit_equity_bridge(base_results.get('projections', {}), assumptions, get_output_path("exit_equity_bridge.png"))
                plot_sources_uses(base_results.get('projections', {}), assumptions, get_output_path("sources_uses.png"))
                plot_sensitivity_heatmap(sens_results, get_output_path("sensitivity_heatmap.png"))
                
                if mc_results_full:
                    plot_monte_carlo_distribution(mc_results_full, get_output_path("monte_carlo.png"))
                
                # Create comprehensive PDF
                create_enhanced_pdf_report(
                    base_results,
                    assumptions,
                    sens_results,
                    mc_results_full,
                    get_output_path("accor_lbo_enhanced.pdf")
                )
                
                st.success("✅ PDF report generated successfully!")
                
                # Offer download
                if (OUT / "accor_lbo_enhanced.pdf").exists():
                    with open(OUT / "accor_lbo_enhanced.pdf", "rb") as pdf_file:
                        st.download_button(
                            label="📥 Download Deal Pack",
                            data=pdf_file.read(),
                            file_name="accor_lbo_enhanced.pdf",
                            mime="application/pdf"
                        )
                
            except Exception as e:
                st.error(f"❌ Error generating PDF: {str(e)}")
    
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
