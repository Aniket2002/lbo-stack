import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import io
import markdown2
from weasyprint import HTML

from src.modules.fund_waterfall import summarize_waterfall, compute_waterfall_by_year
from src.modules.lbo_model import LBOModel

st.set_page_config(page_title="PE Fund Waterfall Studio", layout="wide")
st.title("💰 Private Equity Fund Waterfall Studio")

# ────────────────────────────────────────
# Helper: Markdown → PDF
# ────────────────────────────────────────
def convert_md_to_pdf(md_content: str) -> bytes:
    """
    Convert a Markdown string to PDF bytes using WeasyPrint.
    Always returns bytes, never None.
    """
    # 1) Render Markdown to HTML
    html = markdown2.markdown(md_content)

    # 2) Write PDF into an in-memory buffer
    buffer = io.BytesIO()
    HTML(string=html).write_pdf(buffer)

    # 3) Extract and return the bytes
    return buffer.getvalue()


# ────────────────────────────────────────
# Build Tabs
# ────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📊 Simulator",
    "🧠 Compare Scenarios",
    "📄 Memo + PDF"
])

# ───────────────────────────────
# Tab 1: Full LBO + Fund Simulator
# ───────────────────────────────

with tab1:
    st.header("📊 LBO + Fund Waterfall Simulator")

    # Engine Option in Main Area
    st.markdown("### ⚙️ Engine Options")
    use_lbo = st.checkbox(
        "Use LBO Engine for Distributions",
        value=False,
        help="Override manual distributions using FCFs from your LBO model."
    )

    # Fund Parameters in Sidebar
    with st.sidebar:
        st.header("🧮 Fund Parameters")
        committed_capital = st.number_input("Committed Capital", value=100_000_000)
        gp_commitment = st.slider("GP Commitment (%)", 0.0, 0.2, 0.02, step=0.01)
        mgmt_fee_pct = st.slider("Management Fee (%)", 0.0, 0.05, 0.02, step=0.005)
        reset_hurdle = st.checkbox("Reset Hurdle After Each Tier?", value=False)
        cashless = st.checkbox("Cashless Carry (Accrue only)?", value=False)

        st.markdown("### 📐 Tiered Carry Structure")
        tiers_json = st.text_area(
            "Paste Tiers JSON",
            '[{"hurdle": 0.08, "carry": 0.20}, {"hurdle": 0.12, "carry": 0.30}]',
            height=150
        )

    # LBO Inputs if toggled
    if use_lbo:
        st.markdown("### 🧮 LBO Deal Assumptions")
        col1, col2 = st.columns(2)
        with col1:
            revenue = st.number_input("Initial Revenue", value=50_000_000)
            rev_growth = st.number_input("Revenue Growth (%)", value=0.10)
            ebitda_margin = st.number_input("EBITDA Margin (%)", value=0.20)
            exit_multiple = st.number_input("Exit Multiple", value=8.0)
        with col2:
            capex_pct = st.number_input("CapEx (% of revenue)", value=0.05)
            interest_rate = st.number_input("Interest Rate", value=0.07)
            wc_pct = st.number_input("Working Capital (% of revenue)", value=0.10)
            tax_rate = st.number_input("Tax Rate", value=0.25)

    # Editable Tables for Inputs
    st.markdown("### 📆 Capital Calls & Distributions")
    col1, col2 = st.columns(2)

    calls_default = [committed_capital] + [0] * 4
    dists_default = [0, 0, 0, 0, 160_000_000]

    with col1:
        st.markdown("#### Capital Calls")
        calls_df = st.data_editor(pd.DataFrame({"Capital Call": calls_default}), key="calls")
    with col2:
        st.markdown("#### Distributions")
        dists_df = st.data_editor(pd.DataFrame({"Distribution": dists_default}), key="dists")

    # Run Simulation Button
    if st.button("▶️ Run Simulation"):
        st.write("Running simulation...")


# ───────────────────────────────
# Tab 2: Scenario Comparison
# ───────────────────────────────
with tab2:
    st.header("🧠 Compare Scenarios")
    presets = {
        "Base": {
            "rev_growth":0.10, "exit_mult":8.0,
            "calls":[30e6,30e6,20e6,10e6,0],
            "dists":[0,0,0,0,160e6],
            "tiers":[{"hurdle":0.08,"carry":0.2}]
        },
        "Aggressive": {
            "rev_growth":0.15, "exit_mult":9.0,
            "calls":[25e6,25e6,25e6,25e6,0],
            "dists":[0,0,0,0,200e6],
            "tiers":[{"hurdle":0.08,"carry":0.2},{"hurdle":0.12,"carry":0.3}]
        },
        "Clawback": {
            "rev_growth":0.05, "exit_mult":6.5,
            "calls":[30e6,30e6,20e6,10e6,0],
            "dists":[0,0,0,0,140e6],
            "tiers":[{"hurdle":0.08,"carry":0.2}]
        }
    }
    rows = []
    for name, c in presets.items():
        lbo_res = LBOModel(100e6,0.6,50e6,c["rev_growth"],0.2,0.05,0.10,0.25,c["exit_mult"],0.07).run(years=5)
        fund_res = summarize_waterfall(
            100e6, c["calls"], c["dists"],
            c["tiers"], 0.02, 0.02, False, False
        )
        rows.append({
            "Scenario": name,
            "LBO IRR": round(lbo_res["Exit Summary"]["IRR"]*100,2),
            "Fund IRR": round(fund_res["Net IRR (LP)"]*100,2),
            "MOIC": round(fund_res["MOIC"],2),
            "Clawback": "Yes" if fund_res["Clawback Triggered"] else "No"
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

# ───────────────────────────────
# Tab 3: Memo + PDF + Chart
# ───────────────────────────────
with tab3:
    st.header("📄 Export Memo & PDF")
    scenario = st.selectbox("Choose Scenario", list(presets.keys()))
    s = presets[scenario]
    _ = LBOModel(100e6,0.6,50e6,s["rev_growth"],0.2,0.05,0.10,0.25,s["exit_mult"],0.07).run(5)
    table   = compute_waterfall_by_year(100e6,s["calls"],s["dists"],s["tiers"],0.02,0.02,False,False)
    summary = summarize_waterfall(       100e6,s["calls"],s["dists"],s["tiers"],0.02,0.02,False,False)

    # Generate memo
    def generate_memo(sumry, tbl, name):
        buf = io.StringIO()
        buf.write(f"# 📝 Memo: {name}\n\n")
        buf.write("### Key Metrics\n")
        buf.write(f"- Net IRR (LP): {sumry['Net IRR (LP)']:.2%}\n")
        buf.write(f"- Gross IRR: {sumry['Gross IRR']:.2%}\n")
        buf.write(f"- MOIC: {sumry['MOIC']:.2f}x\n")
        buf.write(f"- Clawback: {'Yes' if sumry['Clawback Triggered'] else 'No'}\n\n")
        buf.write("### Waterfall Table\n\n")
        buf.write(pd.DataFrame(tbl).to_markdown(index=False))
        return buf.getvalue()

    memo = generate_memo(summary, table, scenario)
    st.download_button("📥 Download Memo (.md)", memo, file_name=f"{scenario}_memo.md")

    pdf_data = convert_md_to_pdf(memo)
    st.download_button(
        "📄 Download Memo (.pdf)",
        data=pdf_data,
        file_name=f"{scenario}_memo.pdf",
        mime="application/pdf"
    )

    st.markdown("### 📈 Waterfall Chart")
    df = pd.DataFrame(table)
    df["Total"] = df["LP Share"] + df["GP Share"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["Year"], y=df["LP Share"], name="LP Share"))
    fig.add_trace(go.Bar(x=df["Year"], y=df["GP Share"], name="GP Share"))
    fig.add_trace(go.Scatter(x=df["Year"], y=df["Total"], name="Total", mode="lines+markers"))
    fig.update_layout(
        barmode="stack",
        xaxis_title="Year",
        yaxis_title="Distributions",
        yaxis_tickprefix="$",
        template="ggplot2",
        legend_title="Components"
    )
    st.plotly_chart(fig, use_container_width=True)

# Footer
st.caption("Built by Aniket Bhardwaj — [GitHub](https://github.com/Aniket2002)")
