# LBO Stack 💼

**Comprehensive LBO Model for Financial Analysis**

A sophisticated Python-based LBO model featuring covenant tracking, sensitivity analysis, Monte Carlo simulation, and professional PDF reporting with organized output management.

## 🚀 Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Run the Model

**Command Line:**
```bash
cd src/modules
python orchestrator_advanced.py
```

**Interactive Web App:**
```bash
streamlit run streamlit_app.py
```

### Generated Outputs
All analysis files are automatically saved to the runtime `output/` folder:
- **PDF Report**: Comprehensive analysis document
- **Charts**: Professional visualizations and analysis charts
- **Console**: Detailed financial metrics and results
- **Interactive App**: Real-time assumption testing and live covenant tracking

Reproducible examples and narrative walkthroughs live under `examples/`.

## 📊 Model Features

### Base Case Example
The current example run is driven entirely by the assumptions in `data/accor_assumptions.csv` and the selected UI inputs.

### Advanced Analytics
- **Sensitivity Analysis**: IRR vs **Terminal EBITDA Margin (±400 bps)** and **Exit Multiple (±1.0×)**
- **Monte Carlo**: configurable scenarios with priors and success rule sourced from the current run inputs
- **Deterministic Stress**: Named downside with four outputs (IRR, trough ICR, max ND/EBITDA, Breach Y/N)
- **Equity Cash-Flow Vector**: IRR computed from the exact equity vector printed in the PDF

### Professional Outputs
- Comprehensive PDF reports with executive summary
- Professional chart generation (covenant tracking, exit bridge, deleveraging path)
- Sources & Uses waterfall analysis
- Exit equity bridge visualization
- **Interactive Streamlit app** for real-time scenario analysis

## 📁 Repository Structure

```
lbo-stack/
├── src/modules/
│   ├── orchestrator_advanced.py         # Main LBO model
│   ├── lbo_model.py                     # Core financial modeling
│   └── fund_waterfall.py               # Fund economics and waterfall
├── data/
│   ├── accor_assumptions.csv           # Model assumptions
│   └── accor_historical_recreated.csv  # Historical financial data
├── examples/                           # Reproducible examples and walkthroughs
├── output/                             # Runtime analysis outputs (gitignored)
├── streamlit_app.py                    # Interactive web application
├── requirements.txt                     # Python dependencies
└── README.md                           # This documentation
```

## 📊 Output Files Description

### 📄 PDF Report
Generate the report from the CLI or Streamlit app. The runtime PDF contains:
- Executive summary with key metrics
- Detailed equity cash flow vector analysis
- Embedded charts and visualizations
- Monte Carlo simulation summary
- Sensitivity analysis results table

### 📈 Chart Files

#### Covenant headroom chart
Visual tracking of covenant compliance throughout the investment period:
- Net Debt/EBITDA ratio vs covenant threshold
- Interest Coverage Ratio (ICR) vs minimum requirement
- Color-coded compliance indicators

#### Deleveraging path chart
Debt reduction visualization showing:
- Total debt outstanding over time
- Annual debt paydown amounts
- EBITDA growth trajectory
- Net leverage ratio evolution

#### Exit equity bridge chart
Exit value waterfall chart displaying:
- Enterprise value at exit
- Less: Outstanding debt
- Transaction costs and fees
- Net proceeds to equity investors

#### Monte Carlo chart
Monte Carlo simulation results featuring:
- IRR distribution histogram
- Success rate analysis
- P10/P50/P90 percentile markers
- Risk assessment metrics

#### Sensitivity heatmap
Two-dimensional sensitivity analysis showing:
- IRR sensitivity to **Terminal EBITDA Margin (±400 bps)** and **Exit Multiple (±1.0×)** assumptions
- Color-coded heat map for visual impact assessment
- Base case positioning within scenario range

#### Sources and uses chart
Sources and uses of funds at transaction entry:
- Equity contribution breakdown
- Debt facilities sizing
- Transaction costs allocation
- Total use of funds summary

### 💻 Interactive Web App (`streamlit_app.py`)
Professional Streamlit application featuring:
- **Real-time assumption testing**: Adjust entry/exit multiples, leverage, covenants
- **Live covenant monitoring**: Watch ICR and Net Debt/EBITDA move with assumptions
- **Interactive Monte Carlo**: Configure scenarios (100/200/400) with reproducible seeds
- **One-click PDF generation**: Produces the exact same report as CLI version
- **Professional KPI dashboard**: IRR, MOIC, covenant status with visual indicators

## 🔧 Customization

Edit `data/accor_assumptions.csv` to modify:
- Revenue growth assumptions
- EBITDA margin projections  
- Entry/exit multiples
- Debt structure and pricing
- Covenant levels (defaults: Net Debt/EBITDA ≤ 9.0×, ICR ≥ 2.2×)

## 📈 Analysis Results Summary

The dashboard and PDF now display the current run outputs only. Fixed sample metrics have been removed so the documentation stays synchronized with the model inputs.

## ✅ Why this stands out to PE/IB recruiters
- Lease-adjusted leverage and **explicit covenants** with headroom charts
- **Sources & Uses**, **Exit Equity Bridge**, **Deleveraging Walk** embedded in the PDF
- **Equity cash-flow vector** printed and reconciled to IRR
- Reproducible: one command regenerates the exact PDF; RNG seed pinned
- Unit tests for cash-flow reconciliation, waterfall allocation, and equity-vector consistency
- **Interactive Streamlit app** for live scenario testing and covenant monitoring

## 🏗️ Technical Details

- **Python 3.11+** compatible
- **Pandas/NumPy** for financial modeling
- **Matplotlib** for professional charts with Agg backend
- **FPDF2** for PDF generation
- **Organized output management** with dedicated folder structure

## 📄 License

MIT License - See LICENSE file for details
