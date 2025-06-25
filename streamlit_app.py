import io
import json
import os
from typing import Any, Dict, List, cast

import markdown2
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from weasyprint import HTML

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall
from src.modules.lbo_model import InsolvencyError, LBOModel

os.environ["STREAMLIT_WATCHER_TYPE"] = "poll"

st.set_page_config(page_title="PE Fund Waterfall Studio", layout="wide")
st.title("💰 Private Equity Fund Waterfall Studio")


# ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False, max_entries=5)
def convert_md_to_pdf(memo_md: str) -> bytes:
    """Convert Markdown to PDF (cached)."""
    html = markdown2.markdown(memo_md)
    buf = io.BytesIO()
    HTML(string=html).write_pdf(buf)
    return buf.getvalue()


# ───────────────────────────────────────────────────────────────
with st.sidebar.form("sim_form"):
    st.header("🧮 Fund & Deal Parameters")
    committed_capital = st.number_input(
        "Committed Capital ($)", 100_000_000.0, step=1_000_000.0, format="%.0f"
    )
    debt_pct = st.slider("Leverage (%)", 0.0, 0.95, 0.6, step=0.05)
    gp_commitment = st.slider("GP Commitment (%)", 0.0, 0.2, 0.02, step=0.01)
    mgmt_fee_pct = st.slider("Management Fee (%)", 0.0, 0.05, 0.02, step=0.005)
    reset_hurdle = st.checkbox("Reset Hurdle After Each Tier?", value=False)
    cashless = st.checkbox("Cashless Carry (Accrue only)?", value=False)
    revolver_limit = st.number_input("Revolver Limit ($)", 0.0, step=1_000_000.0)
    revolver_rate = st.number_input("Revolver Rate (%)", 0.0, step=0.01)
    pik_rate = st.number_input("PIK Rate (%)", 0.0, step=0.01)

    st.markdown("### 📐 Tiered Carry Structure")
    default_tiers = (
        '[{"type":"irr","rate":0.08,"carry":0.20}, '
        '{"type":"irr","rate":0.12,"carry":0.30}]'
    )
    tiers_json = st.text_area("Paste Tiers JSON", default_tiers, height=120)

    model_horizon = st.number_input("Model Horizon (yrs)", 1, 20, 5, step=1)
    st.form_submit_button("Apply Settings")


# rebuild tables on horizon change
if (
    "calls_df" not in st.session_state
    or st.session_state.calls_df.shape[0] != model_horizon
):
    base_calls = [committed_capital * (1 - gp_commitment)] + [0.0] * (model_horizon - 1)
    st.session_state.calls_df = pd.DataFrame({"Capital Call": base_calls})

if (
    "dists_df" not in st.session_state
    or st.session_state.dists_df.shape[0] != model_horizon
):
    base_dists = [0.0] * (model_horizon - 1) + [committed_capital * 1.6]
    st.session_state.dists_df = pd.DataFrame({"Distribution": base_dists})


tab1, tab2, tab3 = st.tabs(["📊 Simulator", "🧠 Compare Scenarios", "📄 Memo + PDF"])


# ───────────────────────────────────────────────────────────────
with tab1:
    st.header("📊 LBO + Fund Waterfall Simulator")

    use_lbo = st.checkbox(
        "Use LBO Engine for Distributions",
        value=False,
        help="Override manual distributions using FCFs from your LBO model.",
    )

    st.markdown("### 📆 Capital Calls & Distributions")
    c1, c2 = st.columns(2)

    with c1:
        calls_df = st.data_editor(
            st.session_state.calls_df.copy(),
            key="calls_table",
            use_container_width=True,
        )
    with c2:
        dists_df = st.data_editor(
            st.session_state.dists_df.copy(),
            key="dists_table",
            use_container_width=True,
        )

    try:
        tiers = cast(List[Dict[str, float]], json.loads(tiers_json))
    except Exception:
        st.error("⚠️ Invalid JSON for tiers; please fix.")
        tiers = []

    if calls_df["Capital Call"].sum() > committed_capital * 1.1:
        st.error("❌ Total calls exceed committed capital by >10%!")

    if st.button("▶️ Run Simulation"):
        ev = committed_capital / (1 - debt_pct)
        calls = calls_df["Capital Call"].tolist()
        dists = dists_df["Distribution"].tolist()

        breakdown = compute_waterfall_by_year(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        summary = summarize_waterfall(
            committed_capital,
            calls,
            dists,
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )

        # KPIs vs an 8% hurdle
        hurdle = 0.08
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "LP IRR",
            f"{summary['Net IRR (LP)']: .2%}",
            delta_color="normal" if summary["Net IRR (LP)"] >= hurdle else "off",
        )
        col2.metric("MOIC (LP)", f"{summary['MOIC']: .2f}x")
        gp_carry = summary.get("Cumulative GP Carry", 0.0)
        col3.metric("GP Carry", f"${gp_carry:, }")  # noqa: E231

        st.dataframe(pd.DataFrame(breakdown), use_container_width=True)


# ───────────────────────────────────────────────────────────────
with tab2:
    st.header("🧠 Compare Scenarios")
    presets = {
        "Base": {"rev_growth": 0.10, "exit_mult": 8.0},
        "Aggressive": {"rev_growth": 0.15, "exit_mult": 9.0},
        "Clawback": {"rev_growth": 0.05, "exit_mult": 6.5},
    }

    rows = []
    for name, cfg in presets.items():
        ev = committed_capital / (1 - debt_pct)
        model = LBOModel(
            enterprise_value=ev,
            debt_pct=debt_pct,
            revenue=50e6,
            rev_growth=cfg["rev_growth"],
            ebitda_margin=0.20,
            capex_pct=0.05,
            wc_pct=0.10,
            tax_rate=0.25,
            exit_multiple=cfg["exit_mult"],
            interest_rate=0.07,
            revolver_limit=revolver_limit,
            revolver_rate=revolver_rate,
            pik_rate=pik_rate,
        )
        try:
            lbo_res = model.run(years=model_horizon)
            irr_str = f"{lbo_res['Exit Summary']['IRR']: .2%}"
        except InsolvencyError:
            irr_str = "—"

        fund_res = summarize_waterfall(
            committed_capital,
            calls_df["Capital Call"].tolist(),
            dists_df["Distribution"].tolist(),
            tiers,
            gp_commitment,
            mgmt_fee_pct,
            reset_hurdle=reset_hurdle,
            cashless=cashless,
        )
        rows.append(
            {
                "Scenario": name,
                "LBO IRR": irr_str,
                "Fund IRR": f"{fund_res['Net IRR (LP)']: .2%}",
                "MOIC": f"{fund_res['MOIC']: .2f}x",
                "Clawback": "Yes" if fund_res["Clawback Triggered"] else "No",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ───────────────────────────────────────────────────────────────
with tab3:
    st.header("📄 Export Memo & PDF")
    scenario = st.selectbox("Choose Scenario", list(presets.keys()))
    cfg = presets[scenario]

    ev = committed_capital / (1 - debt_pct)
    model = LBOModel(
        enterprise_value=ev,
        debt_pct=debt_pct,
        revenue=50e6,
        rev_growth=cfg["rev_growth"],
        ebitda_margin=0.20,
        capex_pct=0.05,
        wc_pct=0.10,
        tax_rate=0.25,
        exit_multiple=cfg["exit_mult"],
        interest_rate=0.07,
        revolver_limit=revolver_limit,
        revolver_rate=revolver_rate,
        pik_rate=pik_rate,
    )
    try:
        _ = model.run(years=model_horizon)
    except InsolvencyError:
        pass

    breakdown = compute_waterfall_by_year(
        committed_capital,
        calls_df["Capital Call"].tolist(),
        dists_df["Distribution"].tolist(),
        tiers,
        gp_commitment,
        mgmt_fee_pct,
        reset_hurdle=reset_hurdle,
        cashless=cashless,
    )
    summary = summarize_waterfall(
        committed_capital,
        calls_df["Capital Call"].tolist(),
        dists_df["Distribution"].tolist(),
        tiers,
        gp_commitment,
        mgmt_fee_pct,
        reset_hurdle=reset_hurdle,
        cashless=cashless,
    )

    def generate_memo(
        sumry: Dict[str, Any], tbl: List[Dict[str, Any]], name: str
    ) -> str:
        buf = io.StringIO()
        buf.write(f"# 📝 Memo: {name}\n\n")
        buf.write("### Key Metrics\n")
        buf.write(f"- Net IRR (LP): {sumry['Net IRR (LP)']: .2%}\n")
        gross = sumry.get("Gross IRR", None)
        buf.write(
            f"- Gross IRR: {gross: .2%}\n"
            if gross is not None
            else "- Gross IRR: N/A\n"
        )
        buf.write(f"- MOIC: {sumry['MOIC']: .2f}x\n")
        buf.write(f"- Clawback: {'Yes' if sumry['Clawback Triggered'] else 'No'}\n\n")
        buf.write("### Waterfall Table\n")
        buf.write("<div style='overflow-x:auto'>\n")
        buf.write(pd.DataFrame(tbl).to_markdown(index=False))
        buf.write("\n</div>\n")
        return buf.getvalue()

    memo_md = generate_memo(summary, breakdown, scenario)
    st.download_button(
        "📥 Download Memo (.md)", memo_md, file_name=f"{scenario}_memo.md", key="md_dl"
    )
    st.download_button(
        "📄 Download Memo (.pdf)",
        convert_md_to_pdf(memo_md),
        file_name=f"{scenario}_memo.pdf",
        mime="application/pdf",
        key="pdf_dl",
    )

    st.markdown("### 📈 Waterfall Chart")
    df = pd.DataFrame(breakdown)

    # ────── guard missing LP/GP Share columns ──────
    lp_col = "LP Share" if "LP Share" in df.columns else None
    gp_col = "GP Share" if "GP Share" in df.columns else None
    if lp_col and gp_col:
        df["Total"] = df[lp_col] + df[gp_col]
    else:
        # fallback to sum of all numeric columns
        df["Total"] = df.select_dtypes("number").sum(axis=1)

    fig = go.Figure()
    if lp_col:
        fig.add_trace(go.Bar(x=df["Year"], y=df[lp_col] / 1e6, name="LP Share"))
    if gp_col:
        fig.add_trace(
            go.Bar(
                x=df["Year"],
                y=df[gp_col] / 1e6,
                name="GP Share",
                marker_color=df[gp_col].apply(lambda x: "red" if x < 0 else "green"),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=df["Year"], y=df["Total"] / 1e6, name="Total", mode="lines+markers"
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
