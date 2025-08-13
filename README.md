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

**Quick Monte Carlo (200 scenarios):**
Set MC scenarios to 200 in sidebar for fast testing

**Full Monte Carlo (400 scenarios):**
Set MC scenarios to 400 in sidebar for production runs

### Generated Outputs
All analysis files are automatically saved to the `output/` folder:
- **PDF Report**: Comprehensive analysis document
- **Charts**: Professional visualizations and analysis charts
- **Console**: Detailed financial metrics and results
- **Interactive App**: Real-time assumption testing and live covenant tracking

## 📊 Model Features

### Base Case (Auto-generated example)
- **IRR**: ~11–13% | **MOIC**: ~1.7–2.0× | **Hold**: 5 years
- **Leverage (lease-adjusted)**: ~60–65% of EV at entry
- **Covenants**: Net Debt/EBITDA ≤ **9.0×** (default), ICR ≥ **2.2×** (default) — both configurable in `data/accor_assumptions.csv`
- **IFRS-16**: Lease-in-debt; lease interest included in ICR; lease liability included in net debt at exit
- **Working capital**: **days-based** (AR/AP/deferred revenue)

### Advanced Analytics
- **Sensitivity Analysis**: IRR vs **Terminal EBITDA Margin (±400 bps)** and **Exit Multiple (±1.0×)**
- **Monte Carlo**: **Quick MC (200)** vs **Full MC (400)** scenarios (configurable), with printed priors and success rule:
  σ(growth)=±150 bps, σ(margin)=±200 bps, σ(multiple)=±0.5×; success = no covenant breach + positive exit equity + IRR ≥ 8%
  *Note: PDF and demo use same engine - results never diverge*
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
├── output/                             # Generated analysis outputs
│   ├── accor_lbo_enhanced.pdf          # Comprehensive analysis report
│   ├── covenant_headroom.png           # Covenant compliance tracking
│   ├── deleveraging_path.png           # Debt reduction visualization  
│   ├── exit_equity_bridge.png          # Exit value waterfall chart
│   ├── monte_carlo.png                 # Monte Carlo simulation results
│   ├── sensitivity_heatmap.png         # Sensitivity analysis heatmap
│   └── sources_uses.png               # Sources & uses of funds
├── streamlit_app.py                    # Interactive web application
├── requirements.txt                     # Python dependencies
└── README.md                           # This documentation
```

## 📊 Output Files Description

### 📄 PDF Report (`accor_lbo_enhanced.pdf`)
Comprehensive analysis document containing:
- Executive summary with key metrics
- Detailed equity cash flow vector analysis
- Embedded charts and visualizations
- Monte Carlo simulation summary
- Sensitivity analysis results table

### 📈 Chart Files

#### `covenant_headroom.png`
Visual tracking of covenant compliance throughout the investment period:
- Net Debt/EBITDA ratio vs covenant threshold
- Interest Coverage Ratio (ICR) vs minimum requirement
- Color-coded compliance indicators

#### `deleveraging_path.png` 
Debt reduction visualization showing:
- Total debt outstanding over time
- Annual debt paydown amounts
- EBITDA growth trajectory
- Net leverage ratio evolution

#### `exit_equity_bridge.png`
Exit value waterfall chart displaying:
- Enterprise value at exit
- Less: Outstanding debt
- Transaction costs and fees
- Net proceeds to equity investors

#### `monte_carlo.png`
Monte Carlo simulation results featuring:
- IRR distribution histogram
- Success rate analysis
- P10/P50/P90 percentile markers
- Risk assessment metrics

#### `sensitivity_heatmap.png`
Two-dimensional sensitivity analysis showing:
- IRR sensitivity to **Terminal EBITDA Margin (±400 bps)** and **Exit Multiple (±1.0×)** assumptions
- Color-coded heat map for visual impact assessment
- Base case positioning within scenario range

#### `sources_uses.png`
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

**Sample Results (from run: 2025-08-13, seed=42)**
- Entry Multiple: **8.5×** | Exit Multiple: **9.0–10.0×**
- Target Leverage (lease-adjusted): **~60–65% of EV**
- Max Net Debt/EBITDA (observed): **~7.8–8.4×** vs covenant **9.0×**
- Min ICR (observed): **~2.3–2.6×** vs covenant **2.2×**
- Covenant Status: **Compliant (no breaches)**

**Monte Carlo (N=400, seed=42)**
- Success Rate: **~70–80%**
- Median IRR: **~12–13%**
- P10–P90: **~9–17%**
- Success rule: **no covenant breach + positive exit equity + IRR ≥ 8%**

## ✅ Why this stands out to PE/IB recruiters
- Lease-adjusted leverage and **explicit covenants** with headroom charts
- **Sources & Uses**, **Exit Equity Bridge**, **Deleveraging Walk** embedded in the PDF
- **Equity cash-flow vector** printed and reconciled to IRR
- Reproducible: one command regenerates the exact PDF; RNG seed pinned
- Unit tests for IRR monotonicity and equity-vector reconciliation
- **Interactive Streamlit app** for live scenario testing and covenant monitoring

## 🏗️ Technical Details

- **Python 3.11+** compatible
- **Pandas/NumPy** for financial modeling
- **Matplotlib** for professional charts with Agg backend
- **FPDF2** for PDF generation
- **Organized output management** with dedicated folder structure

## 📄 License

MIT License - See LICENSE file for details
