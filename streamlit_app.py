# streamlit_app.py

import io
from typing import Any, Dict, List, cast

import markdown2
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from weasyprint import HTML

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall
from src.modules.lbo_model import LBOModel

st.set_page_config(page_title="PE Fund Waterfall Studio", layout="wide")
st.title("💰 Private Equity Fund Waterfall Studio")

# ─── Sidebar: Fund & Deal Settings ─────────────────────────────────────────
with st.sidebar.form("fund_settings"):
    st.header("⚙️ Fund & Deal Settings")
    committed_capital = st.number_input(
        "Committed Capital (USD)",
        min_value=0.0,
        value=100_000_000.0,
        step=1e6,
        format="%.0f",
    )
    debt_pct = st.slider("Leverage (Debt % of EV)", 0.1, 0.95, 0.6, step=0.05)
    gp_commitment = st.slider("GP Commitment (%)", 0.0, 0.2, 0.02, step=0.005)
    mgmt_fee_pct = st.slider("Management Fee (%)", 0.0, 0.05, 0.02, step=0.001)
    mgmt_fee_basis = st.selectbox("Mgmt Fee Basis", ["committed", "drawn"])
    reset_hurdle = st.checkbox("Reset Hurdle After Each Tier?", value=False)
    cashless = st.checkbox("Cashless Carry (Accrue only)?", value=False)

    st.markdown("---")
    st.header("🧮 Deal Assumptions")
    revenue0 = st.number_input(
        "Initial Revenue (USD)",
        min_value=0.0,
        value=50_000_000.0,
        step=1e6,
        format="%.0f",
    )
    rev_growth = st.number_input("Revenue Growth (%)", value=0.10, step=0.005)
    ebitda_margin = st.number_input("EBITDA Margin (%)", value=0.20, step=0.005)
    capex_pct = st.number_input("CapEx (% of rev)", value=0.05, step=0.005)
    wc_pct = st.number_input("ΔWC (% of rev)", value=0.10, step=0.005)
    tax_rate = st.number_input("Tax Rate (%)", value=0.25, step=0.005)
    exit_multiple = st.number_input("Exit EBITDA Multiple", value=8.0, step=0.5)
    interest_rate = st.number_input("Interest Rate (%)", value=0.07, step=0.005)
    revolver_limit = st.number_input(
        "Revolver Limit (USD)", min_value=0.0, value=0.0, step=1e6, format="%.0f"
    )
    revolver_rate = st.number_input("Revolver Rate (%)", value=0.0, step=0.001)
    pik_rate = st.number_input("PIK Rate (%)", value=0.0, step=0.001)

    years = st.slider("Model Horizon (years)", 1, 10, 5)
    st.form_submit_button("Apply Settings")

# ─── Handle dynamic calls/dist table length on years change ────────────────
if "prev_years" not in st.session_state or st.session_state.prev_years != years:
    st.session_state.calls_df = pd.DataFrame({"Capital Call": [0.0] * years})
    st.session_state.dists_df = pd.DataFrame({"Distribution": [0.0] * years})
    st.session_state.prev_years = years


# ─── Cache PDF export ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def md_to_pdf(md: str) -> bytes:
    html = markdown2.markdown(md)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()


# ─── Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Simulator", "🧠 Compare Scenarios", "📄 Memo + PDF"])

# ─── Tab 1: Simulator ────────────────────────────────────────────────────────
with tab1:
    st.header("📊 LBO + Fund Waterfall Simulator")

    with st.form("simulator_form"):
        st.subheader("1️⃣ Waterfall Inputs")

        # Tier editor
        tier_df = st.data_editor(
            pd.DataFrame([{"Hurdle": 0.08, "Carry": 0.20}]),
            num_rows="dynamic",
            key="tier_editor",
        )
        hurdles = tier_df["Hurdle"].tolist()
        if hurdles != sorted(hurdles):
            st.error("⚠️ Tiers must be sorted ascending by Hurdle rate.")
        tiers = [
            {"hurdle": float(r["Hurdle"]), "carry": float(r["Carry"])}
            for _, r in tier_df.iterrows()
        ]

        # Capital Calls & Distributions
        c1, c2 = st.columns(2)
        with c1:
            calls_df = st.data_editor(st.session_state.calls_df, key="calls_df")
        with c2:
            dists_df = st.data_editor(st.session_state.dists_df, key="dists_df")

        calls = [float(x) for x in calls_df["Capital Call"]]
        dists = [float(x) for x in dists_df["Distribution"]]

        if sum(calls) > committed_capital:
            st.warning("⚠️ Total capital calls exceed committed capital!")

        run = st.form_submit_button("▶️ Run Simulation")

    if run:
        # Guard EV formula vs debt_pct
        if debt_pct >= 1.0:
            st.error("⚠️ Leverage must be <100 %")
            st.stop()
        ev = committed_capital / (1 - debt_pct)

        model = LBOModel(
            enterprise_value=ev,
            debt_pct=debt_pct,
            revenue=revenue0,
            rev_growth=rev_growth,
            ebitda_margin=ebitda_margin,
            capex_pct=capex_pct,
            wc_pct=wc_pct,
            tax_rate=tax_rate,
            exit_multiple=exit_multiple,
            interest_rate=interest_rate,
            revolver_limit=revolver_limit,
            revolver_rate=revolver_rate,
            pik_rate=pik_rate,
        )
        lbo_res = model.run(years=years)

        breakdown = compute_waterfall_by_year(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            mgmt_fee_basis,
            reset_hurdle,
            cashless,
        )
        summary = summarize_waterfall(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            mgmt_fee_basis,
            reset_hurdle,
            cashless,
        )

        # Persist for Tab 3 and stale-check
        st.session_state.last_summary = summary
        st.session_state.last_breakdown = breakdown

        # Metrics
        threshold = tiers[0]["hurdle"]
        irr_lp = summary["Net IRR (LP)"]
        delta_color = "normal" if irr_lp >= threshold else "inverse"
        st.metric("LBO IRR", f"{lbo_res['Exit Summary']['IRR']:.2%}")
        st.metric("Fund IRR (LP)", f"{irr_lp:.2%}", delta_color=delta_color)
        st.metric("Fund MOIC", f"{summary['MOIC']:.2f}×")

        # Detailed waterfall table
        st.subheader("🔢 Detailed Waterfall by Year")
        df = pd.DataFrame(breakdown)
        st.dataframe(df, use_container_width=True)

        # Distributions chart in $MM
        df_plot = df.copy()
        df_plot["LP Share (MM)"] = df_plot["LP Share"] / 1e6
        gp_mm = df_plot["GP Share"] / 1e6
        df_plot["GP Pos (MM)"] = gp_mm.clip(lower=0)
        df_plot["GP Neg (MM)"] = gp_mm.clip(upper=0)

        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=df_plot["Year"], y=df_plot["LP Share (MM)"], name="LP Share")
        )
        fig.add_trace(
            go.Bar(
                x=df_plot["Year"],
                y=df_plot["GP Pos (MM)"],
                name="GP Carry",
            )
        )
        fig.add_trace(
            go.Bar(
                x=df_plot["Year"],
                y=df_plot["GP Neg (MM)"],
                name="GP Clawback",
                marker_color="crimson",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_plot["Year"],
                y=df_plot["LP Share (MM)"]
                + df_plot["GP Pos (MM)"]
                + df_plot["GP Neg (MM)"],
                mode="lines+markers",
                name="Total",
            )
        )
        fig.update_layout(
            barmode="relative",
            xaxis_title="Year",
            yaxis_title="Distributions ($MM)",
        )
        st.plotly_chart(fig, use_container_width=True)

# ─── Tab 2: Scenario Comparison ───────────────────────────────────────────────
with tab2:
    st.header("🧠 Compare Preset Scenarios")
    presets: Dict[str, Dict[str, Any]] = {
        "Base": {
            "rev_growth": 0.10,
            "exit_multiple": 8.0,
            "calls": [30e6, 30e6, 20e6, 10e6, 0.0],
            "dists": [0.0, 0.0, 0.0, 0.0, 160e6],
            "tiers": [{"hurdle": 0.08, "carry": 0.20}],
        },
        "Aggressive": {
            "rev_growth": 0.15,
            "exit_multiple": 9.0,
            "calls": [25e6, 25e6, 25e6, 25e6, 0.0],
            "dists": [0.0, 0.0, 0.0, 0.0, 200e6],
            "tiers": [
                {"hurdle": 0.08, "carry": 0.20},
                {"hurdle": 0.12, "carry": 0.30},
            ],
        },
        "Clawback": {
            "rev_growth": 0.05,
            "exit_multiple": 6.5,
            "calls": [30e6, 30e6, 20e6, 10e6, 0.0],
            "dists": [0.0, 0.0, 0.0, 0.0, 140e6],
            "tiers": [{"hurdle": 0.08, "carry": 0.20}],
        },
    }
    rows = []
    for name, cfg in presets.items():
        model = LBOModel(
            enterprise_value=committed_capital / (1 - debt_pct),
            debt_pct=debt_pct,
            revenue=revenue0,
            rev_growth=cfg["rev_growth"],
            ebitda_margin=ebitda_margin,
            capex_pct=capex_pct,
            wc_pct=wc_pct,
            tax_rate=tax_rate,
            exit_multiple=cfg["exit_multiple"],
            interest_rate=interest_rate,
            revolver_limit=revolver_limit,
            revolver_rate=revolver_rate,
            pik_rate=pik_rate,
        )
        lbo_res = model.run(years=years)
        fund_res = summarize_waterfall(
            committed_capital,
            cast(List[float], cfg["calls"]),
            cast(List[float], cfg["dists"]),
            cast(List[Dict[str, float]], cfg["tiers"]),
            gp_commitment,
            mgmt_fee_pct,
            mgmt_fee_basis,
            reset_hurdle,
            cashless,
        )
        rows.append(
            {
                "Scenario": name,
                "LBO IRR": f"{lbo_res['Exit Summary']['IRR']:.2%}",
                "Fund IRR": f"{fund_res['Net IRR (LP)']:.2%}",
                "MOIC": f"{fund_res['MOIC']:.2f}×",
                "Clawback": "Yes" if fund_res["Clawback Triggered"] else "No",
            }
        )
    st.table(pd.DataFrame(rows))

# ─── Tab 3: Memo + PDF ──────────────────────────────────────────────────────
with tab3:
    st.header("📄 Memo + PDF Export")

    # Stale‐check: require user to have run simulation since last input tweak
    if "last_summary" not in st.session_state:
        st.error("Please ▶️ Run Simulation in Tab 1 before exporting your memo.")
        st.stop()

    # Recompute a fresh summary to detect input changes
    # (lightweight—just one LBOModel run + waterfall summary)
    if debt_pct < 1.0:
        model = LBOModel(
            enterprise_value=committed_capital / (1 - debt_pct),
            debt_pct=debt_pct,
            revenue=revenue0,
            rev_growth=rev_growth,
            ebitda_margin=ebitda_margin,
            capex_pct=capex_pct,
            wc_pct=wc_pct,
            tax_rate=tax_rate,
            exit_multiple=exit_multiple,
            interest_rate=interest_rate,
            revolver_limit=revolver_limit,
            revolver_rate=revolver_rate,
            pik_rate=pik_rate,
        )
        fresh = summarize_waterfall(
            committed_capital,
            st.session_state.calls_df["Capital Call"].tolist(),
            st.session_state.dists_df["Distribution"].tolist(),
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            mgmt_fee_basis,
            reset_hurdle,
            cashless,
        )
        if fresh != st.session_state.last_summary:  # type: ignore
            st.error(
                "Inputs have changed—please ▶️ Run Simulation again before export."
            )
            st.stop()

    # Build memo markdown
    buf = io.StringIO()
    buf.write("# 📝 Waterfall Memo\n\n")
    buf.write("### Key Metrics\n")
    ls = st.session_state.last_summary  # type: ignore
    buf.write(f"- Net IRR (LP): {ls['Net IRR (LP)']:.2%}\n")
    buf.write(f"- Gross IRR: {ls['Gross IRR']:.2%}\n")
    buf.write(f"- MOIC: {ls['MOIC']:.2f}×\n")
    buf.write(f"- Clawback: {'Yes' if ls['Clawback Triggered'] else 'No'}\n\n")
    buf.write("### Waterfall Table\n\n")
    buf.write(
        pd.DataFrame(st.session_state.last_breakdown).to_markdown(index=False)
    )  # type: ignore

    memo_md = buf.getvalue()

    st.download_button("📥 Download Memo (.md)", memo_md, file_name="waterfall_memo.md")
    pdf_bytes = md_to_pdf(memo_md)
    st.download_button(
        "📄 Download Memo (.pdf)",
        data=pdf_bytes,
        file_name="waterfall_memo.pdf",
        mime="application/pdf",
    )

st.caption("Built by Aniket Bhardwaj — [GitHub](https://github.com/Aniket2002)")
