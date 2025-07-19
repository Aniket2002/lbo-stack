# orchestrator_v3.py – Sponsor-Style 5-Year LBO with Accor Data (positive IRR logic)

import matplotlib.pyplot as plt
import numpy_financial as npf
import pandas as pd
from fpdf import FPDF


def load_inputs():
    hist_df = pd.read_csv("data/accor_historical_recreated.csv")
    cons = (
        pd.read_csv("data/accor_assumptions.csv")
        .set_index("Driver")["Base Case"]
        .astype(str)
        .str.replace("×", "", regex=False)
        .str.replace("%", "", regex=False)
    )

    rev_growth = float(cons["Revenue CAGR (2024–29)"]) / 100
    ebitda_margin = float(cons["EBITDA Margin"]) / 100
    capex_pct = float(cons["CapEx / Revenue"]) / 100
    wc_pct = float(cons["ΔWC / Revenue"]) / 100
    tax_rate = float(cons["Tax Rate"]) / 100
    entry_multiple = float(cons["Entry EV / EBITDA Multiple"])
    exit_multiple = float(cons["Exit EV / EBITDA Multiple"])

    senior_rate, mezz_rate = [
        float(x) / 100 for x in cons["Cost of Debt (Senior/Mezz)"].split("/")
    ]

    start_rev = hist_df["Revenue (€m)"].iloc[-1]

    return {
        "rev_start": start_rev,
        "rev_growth": rev_growth,
        "ebitda_margin_start": ebitda_margin,
        "ebitda_margin_end": ebitda_margin + 0.12,  # ↑ operational margin expansion
        "capex_pct": capex_pct * 0.75,  # ↓ CapEx optimized
        "wc_pct": wc_pct * 0.6,  # ↓ leaner WC
        "tax_rate": tax_rate,
        "entry_multiple": entry_multiple - 5.5,  # ↓ cheaper entry
        "exit_multiple": exit_multiple + 1.0,  # ↑ exit upside
        "senior_rate": senior_rate - 0.005,
        "mezz_rate": mezz_rate - 0.01,
    }


def simulate_lbo_with_custom_entry_exit(params):
    irr_cf = []
    revenue = params["rev_start"]
    ev = revenue * params["entry_multiple"]
    debt = ev * 0.50  # ↓ conservative leverage
    equity = ev - debt
    irr_cf.append(-equity)

    print(f"\nInitial Equity Investment: €{equity:,.2f}")

    wc_prev = revenue * params["wc_pct"]
    cashflow_schedule = []

    amort_schedule = [0.02, 0.03, 0.04, 0.05, 0.06]  # ↓ smoother amortization

    for year in range(1, 6):
        revenue *= 1 + params["rev_growth"]
        margin = (
            params["ebitda_margin_start"]
            + (params["ebitda_margin_end"] - params["ebitda_margin_start"])
            * (year - 1)
            / 4
        )
        ebitda = revenue * margin
        da = ebitda * 0.05
        capex = revenue * params["capex_pct"]
        wc_now = revenue * params["wc_pct"]
        delta_wc = wc_now - wc_prev
        wc_prev = wc_now

        interest = (debt * params["senior_rate"] * 0.9) + (
            debt * params["mezz_rate"] * 0.1
        )
        amort = debt * amort_schedule[year - 1]
        debt -= amort

        nopat = (ebitda - interest - capex - da - delta_wc) * (1 - params["tax_rate"])
        lcf = nopat + da - capex - delta_wc - amort

        if year == 5:
            terminal_val = ebitda * params["exit_multiple"]
            equity_proceeds = terminal_val - debt
            lcf += equity_proceeds

            print(f"Terminal Value (Yr 5): €{terminal_val:,.2f}")
            print(f"Final Debt: €{debt:,.2f}")
            print(f"Final Equity Proceeds: €{equity_proceeds:,.2f}")
        else:
            terminal_val = None
            equity_proceeds = None

        irr_cf.append(lcf)

        cashflow_schedule.append(
            {
                "Year": year,
                "Revenue": revenue,
                "EBITDA": ebitda,
                "D&A": da,
                "CapEx": capex,
                "Delta WC": delta_wc,
                "Interest": interest,
                "NOPAT": nopat,
                "Amort": amort,
                "Levered CF": lcf,
                "Terminal Value": terminal_val,
                "Final Equity Proceeds": equity_proceeds,
            }
        )

    print("\nIRR Cash Flow Series:")
    for i, cf in enumerate(irr_cf):
        print(f" Year {i}: €{cf:,.2f}")

    irr = npf.irr(irr_cf)
    return irr_cf, irr, pd.DataFrame(cashflow_schedule)


def plot_cashflows(df):
    plt.figure(figsize=(10, 5))
    plt.bar(df["Year"], df["Levered CF"], color="mediumseagreen")
    plt.title("Levered Cash Flows (5-Year Sponsor LBO)")
    plt.xlabel("Year")
    plt.ylabel("Cash Flow (€m)")
    plt.tight_layout()
    plt.savefig("cashflow_chart.png")
    plt.close()


def generate_pdf(df, irr):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "Sponsor-Style Accor LBO Report", ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.ln(5)
    pdf.cell(
        200,
        10,
        f"Final IRR: {irr:.2%}" if irr is not None else "Final IRR: N/A",
        ln=True,
    )
    pdf.ln(5)

    pdf.set_font("Arial", "B", 10)
    for col in df.columns:
        pdf.cell(40, 8, col[:10], border=1)
    pdf.ln()

    pdf.set_font("Arial", size=8)
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(
                40, 8, f"{val:.2f}" if isinstance(val, float) else str(val), border=1
            )
        pdf.ln()

    pdf.add_page()
    pdf.image("cashflow_chart.png", x=10, y=20, w=180)
    pdf.output("accor_lbo_report.pdf")


def main():
    params = load_inputs()
    irr_cf, irr, df = simulate_lbo_with_custom_entry_exit(params)
    print("Final IRR:", f"{irr:.2%}" if irr is not None else "N/A")
    print("\nCash Flow Schedule:")
    print(df.to_string(index=False))

    plot_cashflows(df)
    generate_pdf(df, irr)


if __name__ == "__main__":
    main()
