import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import io
import markdown2
from weasyprint import HTML

from src.modules.fund_waterfall import summarize_waterfall, compute_waterfall_by_year
from src.modules.lbo_model import LBOModel

st.set_page_config(page_title="PE Fund Waterfall Simulator", layout="wide")
st.title("💰 Private Equity Fund Waterfall Simulator")

# ========================
# 🧠 Scenario Comparison
# ========================
def compare_presets(presets_dict):
    st.subheader("🧠 Scenario Comparison")
    rows = []
    for name, preset in presets_dict.items():
        lbo = LBOModel(
            enterprise_value=100_000_000,
            debt_pct=0.6,
            revenue=50_000_000,
            rev_growth=preset["rev_growth"],
            ebitda_margin=0.2,
            capex_pct=0.05,
            wc_pct=0.1,
            tax_rate=0.25,
            exit_multiple=preset["exit_mult"],
            interest_rate=0.07
        )
        lbo_result = lbo.run(years=5)
        lbo_irr = lbo_result["Exit Summary"]["IRR"]

        fund_result = summarize_waterfall(
            committed_capital=100_000_000,
            capital_calls=preset["calls"],
            distributions=preset["dists"],
            tiers=preset["tiers"],
            gp_commitment=0.02,
            mgmt_fee_pct=0.02,
            reset_hurdle=False,
            cashless=False
        )
        rows.append({
            "Scenario": name,
            "LBO IRR": round(lbo_irr * 100, 2),
            "Fund IRR (LP)": round(fund_result["Net IRR (LP)"] * 100, 2),
            "MOIC": round(fund_result["MOIC"], 2),
            "Clawback": "Yes" if fund_result["Clawback Triggered"] else "No"
        })
    df_compare = pd.DataFrame(rows)
    st.dataframe(df_compare)

# ========================
# 📄 Markdown Memo Export
# ========================
def generate_memo(summary, table, scenario_name=""):
    memo = io.StringIO()
    memo.write(f"# 📝 Deal Memo: {scenario_name}\n\n")
    memo.write(f"### Key Metrics\n")
    memo.write(f"- Net IRR (LP): {summary['Net IRR (LP)']:.2%}\n")
    memo.write(f"- Gross IRR: {summary['Gross IRR']:.2%}\n")
    memo.write(f"- MOIC: {summary['MOIC']:.2f}x\n")
    memo.write(f"- GP Clawback Triggered: {'Yes' if summary['Clawback Triggered'] else 'No'}\n\n")
    memo.write(f"### Waterfall Table\n\n")
    df = pd.DataFrame(table)
    memo.write(df.to_markdown(index=False))
    return memo.getvalue()

# 🔄 Convert Markdown to PDF
def convert_md_to_pdf(md_content):
    html = markdown2.markdown(md_content)
    pdf_file = io.BytesIO()
    HTML(string=html).write_pdf(pdf_file)
    return pdf_file.getvalue()

# ========================
# 📊 Preset Definitions
# ========================
preset_cases = {
    "Base Case": {
        "rev_growth": 0.10,  # Revenue growth rate
        "exit_mult": 8.0,
        "calls": [30e6, 30e6, 20e6, 10e6, 0],
        "dists": [0, 0, 0, 0, 160e6],
        "tiers": [{"hurdle": 0.08, "carry": 0.2}]
    },
    "Aggressive Exit": {
        "rev_growth": 0.15,
        "exit_mult": 9.0,
        "calls": [25e6, 25e6, 25e6, 25e6, 0],
        "dists": [0, 0, 0, 0, 200e6],
        "tiers": [{"hurdle": 0.08, "carry": 0.2}, {"hurdle": 0.12, "carry": 0.3}]
    },
    "Clawback Trigger": {
        "rev_growth": 0.05,
        "exit_mult": 6.5,
        "calls": [30e6, 30e6, 20e6, 10e6, 0],
        "dists": [0, 0, 0, 0, 140e6],
        "tiers": [{"hurdle": 0.08, "carry": 0.2}]
    }
}

# ========================
# 🚀 Run Scenario Comparison
# ========================
compare_presets(preset_cases)
st.markdown("---")

# ========================
# 📤 Export Memo from One Scenario
# ========================
st.header("📄 Exportable Deal Memo")

chosen = st.selectbox("Choose Scenario for Memo Export", list(preset_cases.keys()))
scenario = preset_cases[chosen]

model = LBOModel(
    enterprise_value=100_000_000,
    debt_pct=0.6,
    revenue=50_000_000,
    rev_growth=scenario["rev_growth"],
    ebitda_margin=0.2,
    capex_pct=0.05,
    wc_pct=0.1,
    tax_rate=0.25,
    exit_multiple=scenario["exit_mult"],
    interest_rate=0.07
)
model.run(years=5)

waterfall_table = compute_waterfall_by_year(
    committed_capital=100_000_000,
    capital_calls=scenario["calls"],
    distributions=scenario["dists"],
    tiers=scenario["tiers"],
    gp_commitment=0.02,
    mgmt_fee_pct=0.02,
    reset_hurdle=False,
    cashless=False
)

summary = summarize_waterfall(
    committed_capital=100_000_000,
    capital_calls=scenario["calls"],
    distributions=scenario["dists"],
    tiers=scenario["tiers"],
    gp_commitment=0.02,
    mgmt_fee_pct=0.02,
    reset_hurdle=False,
    cashless=False
)

# 🔽 Export memo
memo = generate_memo(summary, waterfall_table, scenario_name=chosen)
st.download_button("📥 Download Memo (.md)", memo, file_name=f"{chosen}_memo.md")

pdf_data = convert_md_to_pdf(memo)
st.download_button("📄 Download Memo as PDF", data=pdf_data, file_name=f"{chosen}_memo.pdf", mime="application/pdf")

# ========================
# 📊 Enhanced Waterfall Chart
# ========================
st.markdown("### 📈 LP + GP Share by Year (with Totals)")
df = pd.DataFrame(waterfall_table)
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

# ========================
# 📎 Footer
# ========================
st.caption("Built by Aniket Bhardwaj — [GitHub](https://github.com/Aniket2002)")
