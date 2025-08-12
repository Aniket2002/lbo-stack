# streamlit_app.py
import io
import logging
import os
import time
from typing import Any, Dict, List

import markdown2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from weasyprint import HTML

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall
from src.modules.lbo_model import InsolvencyError, LBOModel

# ── Setup
os.environ["STREAMLIT_WATCHER_TYPE"] = "poll"
logging.basicConfig(level=logging.INFO)
st.set_page_config(page_title="Private Equity Fund Waterfall Studio", layout="wide")
st.title("💰 Private Equity Fund Waterfall Studio")

# ── Default Assumptions
DEFAULTS = {
    "revenue": 50_000_000.0,
    "ebitda_margin": 0.20,
    "capex_pct": 0.05,
    "wc_pct": 0.10,
    "tax_rate": 0.25,
    "exit_multiple": 8.0,
    "interest_rate": 0.07,
    "senior_frac": 0.40,
    "mezz_frac": 0.20,
    "senior_rate": 0.04,
    "mezz_rate": 0.06,
    "rev_growth": 0.10,
    "tiers": [
        {"type": "irr", "rate": 0.08, "carry": 0.20},
        {"type": "irr", "rate": 0.15, "carry": 0.30},
    ],
}


# ── Caching wrappers
@st.cache_data(ttl=3600)
def convert_md_to_pdf(memo_md: str) -> bytes:
    html = markdown2.markdown(memo_md)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()


@st.cache_data(ttl=3600)
def get_waterfall(cc, calls, dists, tiers, **kw):
    return compute_waterfall_by_year(cc, calls, dists, tiers, **kw)


@st.cache_data(ttl=3600)
def get_summary(cc, calls, dists, tiers, **kw):
    return summarize_waterfall(cc, calls, dists, tiers, **kw)


@st.cache_data(ttl=3600)
def run_lbo_model(cfg: Dict[str, Any], years: int = 5):
    allowed = LBOModel.__init__.__code__.co_varnames
    clean = {k: v for k, v in cfg.items() if k in allowed}
    m = LBOModel(**clean)
    return m.run(years=years)


def compare_chart(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        df,
        x="Scenario",
        y=["Fund IRR", "LBO IRR"],
        barmode="group",
        text_auto=True,
        labels={"value": "IRR (%)"},
        title="IRR Comparison by Scenario",
    )
    fig.update_layout(template="simple_white", height=400, legend_title="")
    return fig


# ── Sidebar Inputs
with st.sidebar:
    st.header("Deal Inputs")
    committed_capital = st.number_input(
        "Committed Capital ($)",
        min_value=1e6,
        value=100_000_000.0,
        step=1e6,
        format="%.0f",
        help="Total LP capital in",
    )
    debt_pct = st.slider(
        "Leverage (%)", 0.0, 0.95, 0.7, 0.05, help="Debt / Enterprise Value"
    )
    model_horizon = st.number_input(
        "Model Horizon (yrs)", 1, 20, 5, 1, help="How many years to hold"
    )

    # — Fees & Tiers expander
    with st.expander("Fees & Tiers", expanded=True):
        gp_commitment = st.slider(
            "GP Commitment (%)", 0.0, 0.2, 0.05, 0.01, help="GP co-invest share"
        )
        mgmt_fee_pct = st.slider(
            "Mgmt Fee (%)",
            0.0,
            0.05,
            0.02,
            0.005,
            help="Annual management fee on committed capital",
        )
        reset_hurdle = st.checkbox(
            "Reset Hurdle?", True, help="Reset hurdle after each tier catch-up"
        )
        cashless = st.checkbox(
            "Cashless Carry?", True, help="Defer GP carry until final year"
        )
        st.write("#### Hurdle Tiers")
        tiers_df = st.data_editor(pd.DataFrame(DEFAULTS["tiers"]), key="tiers_editor")
        tiers = tiers_df.to_dict("records")

    # — LBO Assumptions expander
    with st.expander("LBO Assumptions", expanded=False):
        use_lbo = st.checkbox(
            "Use LBO Engine for Distributions",
            False,
            help="Replace manual distributions with full LBO CF",
        )
        revolver_limit = st.number_input(
            "Revolver Limit ($)", 0.0, step=1e6, help="Max revolver capacity"
        )
        revolver_rate = st.number_input(
            "Revolver Rate (%)", 0.0, step=0.01, help="Cost on revolver draws"
        )
        pik_rate = st.number_input(
            "PIK Rate (%)", 0.0, step=0.01, help="PIK interest on bullet"
        )
        rev_growth = st.number_input(
            "Rev Growth (%)",
            0.0,
            1.0,
            DEFAULTS["rev_growth"],
            0.01,
            help="Annual revenue growth",
        )
        exit_multiple = st.number_input(
            "Exit Multiple",
            1.0,
            20.0,
            DEFAULTS["exit_multiple"],
            0.5,
            help="EV/EBITDA multiple at exit",
        )

    # — Advanced Debt Service expander
    with st.expander("Advanced Debt Service", expanded=False):
        st.write("Override the % of original Senior/Mezz balance paid each year:")
        default_sched = {
            "Year": [1, 2, 3, 4, 5],
            "Senior Amort %": [0.05, 0.10, 0.15, 0.30, 0.40],
            "Mezz Amort %": [0.05, 0.10, 0.15, 0.30, 0.40],
        }
        amort_df = st.data_editor(pd.DataFrame(default_sched), key="amort_sched")

# ── initialize calls/distributions
if (
    "calls_df" not in st.session_state
    or len(st.session_state.calls_df) != model_horizon
):
    st.session_state.calls_df = pd.DataFrame(
        {
            "Capital Call": [committed_capital * (1 - gp_commitment)]
            + [0.0] * (model_horizon - 1)
        }
    )
if (
    "dists_df" not in st.session_state
    or len(st.session_state.dists_df) != model_horizon
):
    st.session_state.dists_df = pd.DataFrame(
        {"Distribution": [0.0] * (model_horizon - 1) + [committed_capital * 1.6]}
    )

calls_df = st.session_state.calls_df.copy()
dists_df = st.session_state.dists_df.copy()

# ── Tabs
tab1, tab2, tab3 = st.tabs(["Simulator", "Scenarios", "PDF Report"])

# ─────────────────────────────────────
# TAB 1: SIMULATOR
# ─────────────────────────────────────
with tab1:
    st.header("🛠️ Simulator")
    c1, c2 = st.columns(2)
    calls_df = c1.data_editor(calls_df, key="calls_sim")
    dists_df = c2.data_editor(dists_df, key="dists_sim")

    if st.button("▶️ Run Simulation"):
        calls = calls_df["Capital Call"].tolist()
        dists = dists_df["Distribution"].tolist()

        if use_lbo:
            cfg = {
                "enterprise_value": committed_capital / (1 - debt_pct),
                "debt_pct": debt_pct,
                "senior_frac": DEFAULTS["senior_frac"],
                "mezz_frac": DEFAULTS["mezz_frac"],
                "revenue": DEFAULTS["revenue"],
                "rev_growth": rev_growth,
                "ebitda_margin": DEFAULTS["ebitda_margin"],
                "capex_pct": DEFAULTS["capex_pct"],
                "wc_pct": DEFAULTS["wc_pct"],
                "tax_rate": DEFAULTS["tax_rate"],
                "exit_multiple": exit_multiple,
                "senior_rate": DEFAULTS["senior_rate"],
                "mezz_rate": DEFAULTS["mezz_rate"],
                "revolver_limit": revolver_limit,
                "revolver_rate": revolver_rate,
                "pik_rate": pik_rate,
            }
            try:
                out = run_lbo_model(cfg, model_horizon)
                dists = [
                    out[f"Year {i}"]["Equity CF"] for i in range(1, model_horizon + 1)
                ]
                st.success("✅ Replaced with LBO Equity CFs")
                st.table(
                    pd.DataFrame(
                        {"Year": list(range(1, model_horizon + 1)), "Equity CF": dists}
                    ).style.format({"Equity CF": "${:,.0f}"})
                )
            except InsolvencyError:
                st.warning("⚠️ Debt service plan failed — check your amort schedule.")
                # fall back to manual

        start = time.time()
        wf = get_waterfall(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        summary = get_summary(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        st.success(f"✅ Completed in {time.time()-start:.2f}s")

        m1, m2, m3 = st.columns(3)
        m1.metric("LP IRR", f"{summary['Net IRR (LP)']:.2%}")
        m2.metric("MOIC", f"{summary['MOIC']:.2f}x")
        m3.metric("GP Carry", f"${summary['Cumulative GP Paid']:,}")

        st.subheader("Waterfall by Year")
        df_wf = pd.DataFrame(wf).fillna("–")
        display_cols = [
            c
            for c in [
                "Year",
                "Capital Called",
                "Mgmt Fee",
                "Gross Dist",
                "Net Dist",
                "LP Distributed",
                "GP Paid",
                "GP Accrued",
                "Pre-Fee IRR",
                "Net-Fees IRR",
                "LP IRR",
                "GP IRR",
                "MOIC",
            ]
            if c in df_wf.columns
        ]
        df_show = df_wf[display_cols].copy()
        num_cols = df_show.select_dtypes(include="number").columns
        for col in num_cols:
            col_str = str(col)
            if col_str.endswith("IRR"):
                df_show[col] = df_show[col].round(4)
            else:
                df_show[col] = df_show[col].round(0)
        st.table(df_show)

# ─────────────────────────────────────
# TAB 2: SCENARIOS
# ─────────────────────────────────────
with tab2:
    st.header("🧠 Scenarios")
    presets = {
        "Bear": {"rev_growth": 0.02, "exit_mult": 5.0},
        "Base": {"rev_growth": 0.10, "exit_mult": DEFAULTS["exit_multiple"]},
        "Bull": {"rev_growth": 0.20, "exit_mult": 11.0},
    }
    rows: List[Dict[str, Any]] = []
    for name, p in presets.items():
        cfg = {
            "enterprise_value": committed_capital / (1 - debt_pct),
            "debt_pct": debt_pct,
            "senior_frac": DEFAULTS["senior_frac"],
            "mezz_frac": DEFAULTS["mezz_frac"],
            "revenue": DEFAULTS["revenue"],
            "rev_growth": p["rev_growth"],
            "ebitda_margin": DEFAULTS["ebitda_margin"],
            "capex_pct": DEFAULTS["capex_pct"],
            "wc_pct": DEFAULTS["wc_pct"],
            "tax_rate": DEFAULTS["tax_rate"],
            "exit_multiple": p["exit_mult"],
            "senior_rate": DEFAULTS["senior_rate"],
            "mezz_rate": DEFAULTS["mezz_rate"],
            "revolver_limit": revolver_limit if use_lbo else 0.0,
            "revolver_rate": revolver_rate if use_lbo else 0.0,
            "pik_rate": pik_rate if use_lbo else 0.0,
        }
        try:
            out = run_lbo_model(cfg, model_horizon)
            irr_lbo = out["Exit Summary"]["IRR"] or 0.0
            eq_cfs = [
                out[f"Year {i}"]["Equity CF"] for i in range(1, model_horizon + 1)
            ]
        except InsolvencyError:
            irr_lbo = 0.0
            eq_cfs = [0.0] * model_horizon

        calls_s = [committed_capital * (1 - gp_commitment)] + [0.0] * (
            model_horizon - 1
        )
        fund = get_summary(
            committed_capital,
            calls_s,
            eq_cfs,
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        rows.append(
            {
                "Scenario": name,
                "LBO IRR": f"{irr_lbo:.1%}",
                "Fund IRR": f"{fund['Net IRR (LP)']:.1%}",
                "MOIC": f"{fund['MOIC']:.2f}x",
            }
        )
    df_comp = pd.DataFrame(rows)
    st.dataframe(df_comp, use_container_width=True)
    st.plotly_chart(compare_chart(df_comp), use_container_width=True)

# ─────────────────────────────────────
# TAB 3: PDF REPORT
# ─────────────────────────────────────
with tab3:
    st.header("📄 PDF Report")
    if st.button("Generate & Download PDF"):
        wf = get_waterfall(
            committed_capital,
            calls_df["Capital Call"].tolist(),
            dists_df["Distribution"].tolist(),
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        summary = get_summary(
            committed_capital,
            calls_df["Capital Call"].tolist(),
            dists_df["Distribution"].tolist(),
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        md = (
            "## LBO Summary\n\n"
            f"- {int(debt_pct*100)}% leverage, exit @ {exit_multiple:.1f}× EBITDA\n"
            f"- LP IRR: {summary['Net IRR (LP)']:.1%}, MOIC: {summary['MOIC']:.2f}x\n\n"
            "### Waterfall\n\n" + pd.DataFrame(wf).to_markdown(index=False)
        )
        pdf = convert_md_to_pdf(md)
        st.download_button(
            "📥 Download PDF", pdf, file_name="lbo_report.pdf", mime="application/pdf"
        )
