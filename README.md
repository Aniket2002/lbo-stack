# LBO Stack 💼

**VP-Grade LBO Model for Professional Deal Analysis**

A comprehensive Python-based LBO model with institutional-quality features including covenant tracking, sensitivity analysis, Monte Carlo simulation, and professional PDF reporting.

## 🚀 Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Run the Model
```bash
cd src/modules
python orchestrator_advanced.py
```

### Output
- **PDF Report**: `accor_lbo_enhanced.pdf` 
- **Charts**: Covenant tracking, sensitivity analysis, Monte Carlo results
- **Console**: Detailed financial metrics and analysis

## 📊 Model Features

### Base Case Analysis
- **IRR**: 9.1% | **MOIC**: 1.7x | **Investment Period**: 5 years
- VP-grade covenant tracking (Net Debt/EBITDA, ICR)
- IFRS-16 lease liability treatment
- Professional working capital modeling

### Advanced Analytics
- **Sensitivity Analysis**: 2D heatmaps (Revenue Growth vs Exit Multiple)
- **Monte Carlo Simulation**: 400+ scenarios with explicit priors
- **Deterministic Stress Testing**: Named downside scenarios
- **Equity Cash Flow Vector**: Transparent IRR calculation

### Professional Outputs
- IC-ready PDF reports with executive summary
- Professional chart generation (covenant tracking, exit bridge, deleveraging path)
- Sources & Uses waterfall analysis
- Exit equity bridge visualization

## 📁 Repository Structure

```
lbo-stack/
├── src/modules/orchestrator_advanced.py  # Main VP-grade LBO model
├── data/
│   ├── accor_assumptions.csv             # Model assumptions
│   └── accor_historical_recreated.csv    # Historical financial data
├── requirements.txt                       # Python dependencies
└── README.md                             # This file
```

## 🔧 Customization

Edit `data/accor_assumptions.csv` to modify:
- Revenue growth assumptions
- EBITDA margin projections  
- Entry/exit multiples
- Debt structure and pricing
- Covenant levels

## 📈 Results Summary

**Base Case (Accor Hotel Portfolio)**
- Entry Multiple: 8.5x EBITDA
- Exit Multiple: 10.0x EBITDA
- Target Leverage: 85% of Enterprise Value
- Maximum Net Debt/EBITDA: 6.1x (vs 7.0x covenant)
- Minimum ICR: 2.8x (vs 2.5x covenant)
- Covenant Status: COMPLIANT

## 🏗️ Technical Details

- **Python 3.11+** compatible
- **Pandas/NumPy** for financial modeling
- **Matplotlib** for professional charts
- **FPDF2** for PDF generation
- **VP-grade semantic fixes** applied throughout

## 📄 License

MIT License - See LICENSE file for details
