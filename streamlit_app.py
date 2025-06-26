# === IMPORTS & CONFIG ===
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

os.environ["STREAMLIT_WATCHER_TYPE"] = "poll"
logging.basicConfig(level=logging.INFO)

# === DEFAULTS ===
# Updated to 2/20 demo with super-carry tier
DEFAULTS = {
    "revenue": 50_000_000.0,
    "ebitda_margin": 0.20,
    "capex_pct": 0.05,
    "wc_pct": 0.10,
    "tax_rate": 0.25,
    "exit_multiple": 8.0,
    "interest_rate": 0.07,
    "hurdle": 0.08,
    "rev_growth": 0.10,
    "tiers": [
        {"type": "irr", "rate": 0.08, "carry": 0.20},  # 8% hurdle @20% carry
        {"type": "irr", "rate": 0.15, "carry": 0.30},  # 15% hurdle @30% carry
    ],
}

st.set_page_config(page_title="PE Fund Waterfall Studio", layout="wide")
st.title("💰 Private Equity Fund Waterfall Studio")


# === CACHING HELPERS ===
@st.cache_data(ttl=3600)
def convert_md_to_pdf(memo_md: str) -> bytes:
    html = markdown2.markdown(memo_md)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()


@st.cache_data(ttl=3600)
def get_waterfall(committed_capital, calls, dists, tiers, **kwargs):
    return compute_waterfall_by_year(committed_capital, calls, dists, tiers, **kwargs)


@st.cache_data(ttl=3600)
def get_summary(committed_capital, calls, dists, tiers, **kwargs):
    return summarize_waterfall(committed_capital, calls, dists, tiers, **kwargs)


@st.cache_data(ttl=3600)
def run_lbo_model(config: Dict[str, Any], years: int = 5):
    allowed = LBOModel.__init__.__code__.co_varnames
    clean_cfg = {k: v for k, v in config.items() if k in allowed}
    model = LBOModel(**clean_cfg)
    return model.run(years=years)


# === UTIL FUNCTIONS ===
def compare_scenarios_chart(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        df,
        x="Scenario",
        y=["Fund IRR", "LBO IRR"],
        barmode="group",
        labels={"value": "IRR (%)", "variable": "Metric"},
        text_auto=True,
        title="IRR Comparison by Scenario",
    )
    fig.update_layout(template="simple_white", height=400, legend_title="")
    return fig


# === SIDEBAR ===
with st.sidebar:
    st.header("📘 Deal & Waterfall Inputs")
    # 2/20 demo defaults
    committed_capital = st.number_input(
        "Committed Capital ($)", 1e6, value=100_000_000.0, step=1e6, format="%.0f"
    )
    debt_pct = st.slider("Leverage (%)", 0.0, 0.95, value=0.7, step=0.05)
    model_horizon = st.number_input("Model Horizon (yrs)", 1, 20, value=7, step=1)

    st.subheader("Fees & Tiers")
    gp_commitment = st.slider("GP Commitment (%)", 0.0, 0.2, value=0.05, step=0.01)
    mgmt_fee_pct = st.slider("Mgmt Fee (%)", 0.0, 0.05, value=0.02, step=0.005)
    reset_hurdle = st.checkbox("Reset Hurdle?", value=True)
    cashless = st.checkbox("Cashless Carry?", value=True)
    tiers = st.data_editor(pd.DataFrame(DEFAULTS["tiers"]), key="tiers_editor").to_dict(
        "records"
    )

    use_lbo = st.checkbox("Use LBO Engine for Distributions", value=False)
    if use_lbo:
        st.subheader("LBO Assumptions")
        revolver_limit = st.number_input("Revolver Limit ($)", 0.0, step=1e6)
        revolver_rate = st.number_input("Revolver Rate (%)", 0.0, step=0.01)
        pik_rate = st.number_input("PIK Rate (%)", 0.0, step=0.01)
        rev_growth = st.number_input(
            "Rev Growth (%)", 0.0, 1.0, DEFAULTS["rev_growth"], step=0.01
        )
        exit_multiple = st.number_input(
            "Exit Multiple", 1.0, 20.0, DEFAULTS["exit_multiple"], step=0.5
        )
    else:
        revolver_limit = revolver_rate = pik_rate = rev_growth = exit_multiple = 0.0

# === DATAFRAME INIT ===
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

# === TABS ===
tab1, tab2, tab3 = st.tabs(["📊 Simulator", "🧠 Compare Scenarios", "📄 Memo + PDF"])

# === TAB 1: Simulator ===
with tab1:
    st.header("📊 LBO + Fund Waterfall Simulator")
    c1, c2 = st.columns(2)
    calls_df = c1.data_editor(calls_df, key="calls_sim")
    dists_df = c2.data_editor(dists_df, key="dists_sim")

    if calls_df["Capital Call"].sum() > committed_capital * 1.1:
        st.error("❌ Calls exceed committed capital by >10%!")

    if st.button("▶️ Run Simulation"):
        calls = calls_df["Capital Call"].tolist()
        dists = dists_df["Distribution"].tolist()

        if use_lbo:
            cfg = {
                "enterprise_value": committed_capital / (1 - debt_pct),
                "debt_pct": debt_pct,
                "revenue": DEFAULTS["revenue"],
                "rev_growth": rev_growth,
                "ebitda_margin": DEFAULTS["ebitda_margin"],
                "capex_pct": DEFAULTS["capex_pct"],
                "wc_pct": DEFAULTS["wc_pct"],
                "tax_rate": DEFAULTS["tax_rate"],
                "exit_multiple": exit_multiple,
                "interest_rate": DEFAULTS["interest_rate"],
                "revolver_limit": revolver_limit,
                "revolver_rate": revolver_rate,
                "pik_rate": pik_rate,
            }
            try:
                lbo_res = run_lbo_model(cfg, model_horizon)
                dists = [
                    lbo_res[f"Year {i}"]["Equity CF"]
                    for i in range(1, model_horizon + 1)
                ]
                st.success("✅ Replaced with LBO Equity CFs")
                # Display as table
                cf_df = pd.DataFrame(
                    {"Year": list(range(1, model_horizon + 1)), "Equity CF": dists}
                )
                cf_df["Equity CF"] = cf_df["Equity CF"].map(lambda x: f"${x:,.0f}")
                st.table(cf_df)
            except InsolvencyError as e:
                st.error(f"LBO failed: {e}")
                st.stop()

        start = time.time()
        breakdown = get_waterfall(
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

        st.dataframe(pd.DataFrame(breakdown), use_container_width=True)

# === TAB 2: Compare Scenarios ===
with tab2:
    st.header("🧠 Compare Scenarios")
    presets = {
        "Bear Case": {"rev_growth": 0.02, "exit_mult": 5.0},  # loss + clawback
        "Base Case": {"rev_growth": 0.10, "exit_mult": 8.0},  # clears 8% hurdle
        "Bull Case": {"rev_growth": 0.20, "exit_mult": 10.0},  # hits 2nd tier carry
    }

    rows: List[Dict[str, Any]] = []
    base_fund_irr = None
    for name, p in presets.items():
        cfg = {
            "enterprise_value": committed_capital / (1 - debt_pct),
            "debt_pct": debt_pct,
            "revenue": DEFAULTS["revenue"],
            "rev_growth": p["rev_growth"],
            "ebitda_margin": DEFAULTS["ebitda_margin"],
            "capex_pct": DEFAULTS["capex_pct"],
            "wc_pct": DEFAULTS["wc_pct"],
            "tax_rate": DEFAULTS["tax_rate"],
            "exit_multiple": p["exit_mult"],
            "interest_rate": DEFAULTS["interest_rate"],
            "revolver_limit": 0,
            "revolver_rate": 0,
            "pik_rate": 0,
        }
        try:
            lbo_res = run_lbo_model(cfg, years=model_horizon)
            cf_vals = [
                lbo_res[f"Year {i}"]["Equity CF"] for i in range(1, model_horizon + 1)
            ]
            cf_df = pd.DataFrame(
                {"Year": range(1, model_horizon + 1), "Equity CF": cf_vals}
            )
            cf_df["Equity CF"] = cf_df["Equity CF"].map(lambda x: f"${x:,.0f}")
            st.subheader(f"Equity CFs ({name})")
            st.table(cf_df)
            irr_lbo = lbo_res["Exit Summary"]["IRR"] or 0.0
        except Exception:
            irr_lbo = 0.0
            cf_vals = [0.0] * model_horizon

        calls_s = [committed_capital * (1 - gp_commitment)] + [0.0] * (
            model_horizon - 1
        )
        fund = get_summary(
            committed_capital,
            calls_s,
            cf_vals,
            tiers,
            gp_commitment=gp_commitment,
            mgmt_fee_pct=mgmt_fee_pct,
        )
        irr_fund = fund["Net IRR (LP)"] * 100
        if name == "Base":
            base_fund_irr = irr_fund

        rows.append(
            {
                "Scenario": name,
                "LBO IRR": round(irr_lbo * 100, 2),
                "Fund IRR": round(irr_fund, 2),
                "MOIC": round(fund["MOIC"], 2),
                "Clawback": "✅" if not fund["Clawback Triggered"] else "❌",
                "Comment": (
                    "—"
                    if name == "Base"
                    else (
                        "📈 Better than base"
                        if base_fund_irr is not None and irr_fund > base_fund_irr
                        else "📉 Worse than base"
                    )
                ),
            }
        )

    df_comp = pd.DataFrame(rows)
    st.dataframe(
        df_comp.style.highlight_max(
            axis=0, subset=["Fund IRR", "MOIC"], color="lightgreen"
        ),
        use_container_width=True,
    )
    st.plotly_chart(compare_scenarios_chart(df_comp), use_container_width=True)

# === TAB 3: Memo + PDF ===
with tab3:
    st.header("📄 Export Memo & PDF")
    scenario = st.selectbox("Choose Scenario", list(presets.keys()))
    p = presets[scenario]
    try:
        model_cfg = {
            **DEFAULTS,
            "enterprise_value": committed_capital / (1 - debt_pct),
            "debt_pct": debt_pct,
            "rev_growth": p["rev_growth"],
            "exit_multiple": p["exit_mult"],
            "revolver_limit": revolver_limit,
            "revolver_rate": revolver_rate,
            "pik_rate": pik_rate,
        }
        res = run_lbo_model(model_cfg, years=model_horizon)
        dists_m = [res[f"Year {i}"]["Equity CF"] for i in range(1, model_horizon + 1)]
    except InsolvencyError:
        dists_m = dists_df["Distribution"].tolist()

    breakdown = get_waterfall(
        committed_capital,
        calls_df["Capital Call"].tolist(),
        dists_m,
        tiers,
        gp_commitment=gp_commitment,
        mgmt_fee_pct=mgmt_fee_pct,
        reset_hurdle=reset_hurdle,
        cashless=cashless,
    )
    summary = get_summary(
        committed_capital,
        calls_df["Capital Call"].tolist(),
        dists_m,
        tiers,
        gp_commitment=gp_commitment,
        mgmt_fee_pct=mgmt_fee_pct,
        reset_hurdle=reset_hurdle,
        cashless=cashless,
    )

    def gen_memo(s, tbl, name):
        buf = io.StringIO()
        buf.write(f"# 📝 Memo: {name}\n\n")
        buf.write("### Key Metrics\n")
        buf.write(f"- Net IRR (LP): {s['Net IRR (LP)']: .2%}\n")
        buf.write(f"- MOIC: {s['MOIC']: .2f}x\n")
        buf.write(f"- Clawback: {'Yes' if s['Clawback Triggered'] else 'No'}\n\n")
        buf.write("### Waterfall Table\n")
        buf.write(pd.DataFrame(tbl).to_markdown(index=False))
        return buf.getvalue()

    memo = gen_memo(summary, breakdown, scenario)
    st.download_button("📥 Download Memo (.md)", memo, file_name=f"{scenario}_memo.md")
    st.download_button(
        "📄 Download Memo (.pdf)",
        convert_md_to_pdf(memo),
        file_name=f"{scenario}_memo.pdf",
        mime="application/pdf",
    )

    st.markdown("### 📈 Waterfall Chart")
    df = pd.DataFrame(breakdown)
    fig = go.Figure()
    for col in ["LP Share", "GP Share"]:
        if col in df.columns:
            fig.add_trace(go.Bar(x=df["Year"], y=df[col] / 1e6, name=col))
    fig.add_trace(
        go.Scatter(
            x=df["Year"],
            y=df.select_dtypes(float).sum(axis=1) / 1e6,
            name="Total",
            mode="lines+markers",
        )
    )
    fig.update_layout(
        barmode="stack",
        xaxis_title="Year",
        yaxis_title="Distributions ($MM)",
        legend_title="Components",
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption("Built by Aniket Bhardwaj — [GitHub](https://github.com/Aniket2002)")
