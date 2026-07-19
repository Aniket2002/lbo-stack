from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from .orchestrator_advanced import (
        DealAssumptions,
        build_canonical_sources_and_uses,
        build_exit_equity_bridge,
        create_enhanced_pdf_report,
        enhanced_sensitivity_grid,
        get_output_path,
        monte_carlo_analysis,
        plot_covenant_headroom,
        plot_deleveraging_path,
        plot_exit_equity_bridge,
        plot_monte_carlo_results,
        plot_sensitivity_heatmap,
        plot_sources_and_uses,
        run_enhanced_base_case,
    )
except ImportError:  # pragma: no cover - direct Streamlit execution
    from orchestrator_advanced import (
        DealAssumptions,
        build_canonical_sources_and_uses,
        build_exit_equity_bridge,
        create_enhanced_pdf_report,
        enhanced_sensitivity_grid,
        get_output_path,
        monte_carlo_analysis,
        plot_covenant_headroom,
        plot_deleveraging_path,
        plot_exit_equity_bridge,
        plot_monte_carlo_results,
        plot_sensitivity_heatmap,
        plot_sources_and_uses,
        run_enhanced_base_case,
    )

st.set_page_config(
    page_title="LBO Stack",
    page_icon="💼",
    layout="wide",
)

st.title("LBO Stack")
st.caption(
    "Annual LBO scenario analysis with explicit cash, debt, revolver, "
    "covenant and exit-equity reconciliation."
)

with st.sidebar.form("deal_assumptions"):
    st.subheader("Valuation")
    entry_multiple = st.number_input(
        "Entry EV / EBITDA",
        min_value=3.0,
        max_value=20.0,
        value=8.5,
        step=0.1,
    )
    exit_multiple = st.number_input(
        "Exit EV / EBITDA",
        min_value=3.0,
        max_value=20.0,
        value=10.0,
        step=0.1,
    )
    sale_cost = st.number_input(
        "Sale costs",
        min_value=0.0,
        max_value=0.10,
        value=0.01,
        step=0.005,
        format="%.3f",
    )

    st.subheader("Operating case")
    revenue = st.number_input(
        "Opening revenue",
        min_value=1.0,
        value=5_000.0,
        step=100.0,
    )
    revenue_growth = st.number_input(
        "Annual revenue growth",
        min_value=-0.20,
        max_value=0.30,
        value=0.04,
        step=0.005,
        format="%.3f",
    )
    opening_margin = st.number_input(
        "Opening EBITDA margin",
        min_value=0.01,
        max_value=0.80,
        value=0.22,
        step=0.005,
        format="%.3f",
    )
    terminal_margin = st.number_input(
        "Terminal EBITDA margin",
        min_value=0.01,
        max_value=0.80,
        value=0.25,
        step=0.005,
        format="%.3f",
    )

    st.subheader("Capital structure")
    debt_pct = st.slider(
        "Financial debt / entry EV",
        min_value=0.0,
        max_value=0.85,
        value=0.60,
        step=0.01,
    )
    senior_rate = st.number_input(
        "Senior cash interest rate",
        min_value=0.0,
        max_value=0.30,
        value=0.045,
        step=0.005,
        format="%.3f",
    )
    mezz_rate = st.number_input(
        "Mezzanine cash interest rate",
        min_value=0.0,
        max_value=0.40,
        value=0.08,
        step=0.005,
        format="%.3f",
    )
    revolver_limit = st.number_input(
        "Revolver capacity",
        min_value=0.0,
        value=200.0,
        step=25.0,
    )
    minimum_cash = st.number_input(
        "Minimum retained cash",
        min_value=0.0,
        value=150.0,
        step=25.0,
    )
    cash_sweep = st.slider(
        "Optional cash sweep",
        min_value=0.0,
        max_value=1.0,
        value=0.85,
        step=0.05,
    )

    st.subheader("Lease and risk")
    lease_multiple = st.number_input(
        "Opening IFRS-16 liability / EBITDA",
        min_value=0.0,
        max_value=10.0,
        value=3.2,
        step=0.1,
    )
    lease_amort_years = st.number_input(
        "Lease-liability amortisation years",
        min_value=1,
        max_value=40,
        value=15,
        step=1,
    )
    monte_carlo_paths = st.selectbox(
        "Monte Carlo paths",
        options=[100, 200, 400],
        index=1,
    )
    submitted = st.form_submit_button("Run analysis", type="primary")

if not submitted:
    st.info("Set the assumptions in the sidebar and select **Run analysis**.")
    st.stop()

assumptions = DealAssumptions(
    entry_ev_ebitda=float(entry_multiple),
    exit_ev_ebitda=float(exit_multiple),
    sale_cost_pct=float(sale_cost),
    revenue0=float(revenue),
    rev_growth_geo=float(revenue_growth),
    ebitda_margin_start=float(opening_margin),
    ebitda_margin_end=float(terminal_margin),
    debt_pct_of_ev=float(debt_pct),
    senior_rate=float(senior_rate),
    mezz_rate=float(mezz_rate),
    revolver_limit=float(revolver_limit),
    min_cash=float(minimum_cash),
    cash_sweep_pct=float(cash_sweep),
    lease_liability_mult_of_ebitda=float(lease_multiple),
    lease_amort_years=int(lease_amort_years),
)

results, metrics = run_enhanced_base_case(assumptions)
if "Error" in results:
    st.error(results["Error"])
    st.stop()

sources_and_uses = build_canonical_sources_and_uses(assumptions)
exit_bridge = build_exit_equity_bridge(results, metrics, assumptions)
sensitivity = enhanced_sensitivity_grid(assumptions)
mc_results = monte_carlo_analysis(
    assumptions,
    n=int(monte_carlo_paths),
    seed=42,
)

irr = metrics.get("IRR")
columns = st.columns(5)
columns[0].metric("IRR", "n/a" if irr is None else f"{irr:.1%}")
columns[1].metric("MOIC", f"{metrics['MOIC']:.2f}x")
columns[2].metric("Exit equity", f"{metrics['Equity Value']:,.0f}")
columns[3].metric("Minimum ICR", f"{metrics['Min_ICR']:.2f}x")
columns[4].metric("Maximum net leverage", f"{metrics['Max_Leverage']:.2f}x")

st.subheader("Financial projections")
projection_rows = []
for year in range(1, assumptions.years + 1):
    row = results[f"Year {year}"]
    projection_rows.append(
        {
            "Year": year,
            "Revenue": row["Revenue"],
            "EBITDA": row["EBITDA"],
            "Operating cash generation": row["Operating Cash Generation"],
            "Cash interest": row["Cash Interest"],
            "PIK interest": row["PIK Interest"],
            "Mandatory amortisation": row["Actual Amortization"],
            "Optional sweep": row["Optional Cash Sweep"],
            "Revolver draws": row["Debt Draws"],
            "Closing debt": row["Closing Debt"],
            "Closing cash": row["Closing Cash"],
        }
    )
st.dataframe(pd.DataFrame(projection_rows), use_container_width=True)

first_tab, second_tab, third_tab, fourth_tab = st.tabs(
    ["Transaction", "Covenants", "Sensitivity", "Monte Carlo"]
)

with first_tab:
    left, right = st.columns(2)
    with left:
        st.pyplot(plot_sources_and_uses(assumptions), clear_figure=True)
        st.json(
            {
                "sources": sources_and_uses["sources"],
                "uses": sources_and_uses["uses"],
                "sources_equal_uses": sources_and_uses[
                    "sources_equals_uses"
                ],
            }
        )
    with right:
        st.pyplot(
            plot_exit_equity_bridge(results, metrics, assumptions),
            clear_figure=True,
        )
        st.json(exit_bridge)
    st.pyplot(
        plot_deleveraging_path(results, assumptions),
        clear_figure=True,
    )

with second_tab:
    st.pyplot(
        plot_covenant_headroom(metrics, assumptions),
        clear_figure=True,
    )
    st.write(
        {
            "ICR breach": metrics["ICR_Breach"],
            "Leverage breach": metrics["Leverage_Breach"],
            "FCF coverage breach": metrics["FCF_Breach"],
            "Debt reconciliation delta": metrics[
                "Debt_Roll_Forward_Max_Delta"
            ],
            "Cash reconciliation delta": metrics[
                "Cash_Roll_Forward_Max_Delta"
            ],
        }
    )

with third_tab:
    st.pyplot(
        plot_sensitivity_heatmap(sensitivity),
        clear_figure=True,
    )
    st.dataframe(sensitivity.style.format("{:.1%}"), use_container_width=True)

with fourth_tab:
    st.pyplot(
        plot_monte_carlo_results(mc_results),
        clear_figure=True,
    )
    mc_columns = st.columns(4)
    mc_columns[0].metric("Success rate", f"{mc_results['Success_Rate']:.1%}")
    mc_columns[1].metric("Median IRR", f"{mc_results['Median_IRR']:.1%}")
    mc_columns[2].metric("P10 IRR", f"{mc_results['P10_IRR']:.1%}")
    mc_columns[3].metric("P90 IRR", f"{mc_results['P90_IRR']:.1%}")
    st.caption(mc_results["SuccessDef"])

analysis_for_pdf = {
    "metrics": metrics,
    "sources_and_uses": sources_and_uses,
}
pdf_path = create_enhanced_pdf_report(
    analysis_for_pdf,
    get_output_path("lbo_analysis.pdf"),
)
pdf_bytes = Path(pdf_path).read_bytes()
st.download_button(
    "Download PDF summary",
    data=pdf_bytes,
    file_name="lbo_analysis.pdf",
    mime="application/pdf",
)

if not math.isfinite(metrics["Debt_Roll_Forward_Max_Delta"]):
    st.warning("Debt reconciliation returned a non-finite value.")
