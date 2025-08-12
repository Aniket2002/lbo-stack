<h1 align="center">
  LBO-Stack 🦄
</h1>

<p align="center">
  <em>Deal-grade analytics  |  Partner-grade transparency  |  Push-button storytelling</em>
</p>

<p align="center">
  <!-- CI & coverage badges retained -->
  <a href="https://github.com/Aniket2002/lbo-stack/actions/workflows/ci.yml">
    <img alt="CI Status" src="https://img.shields.io/github/actions/workflow/status/Aniket2002/lbo-stack/ci.yml?label=CI&logo=github">
  </a>
  <a href="https://codecov.io/gh/Aniket2002/lbo-stack">
    <img alt="Coverage" src="https://img.shields.io/codecov/c/github/Aniket2002/lbo-stack?logo=codecov">
  </a>
  <!-- ▶️ Live demo badge updated -->
  <a href="https://aniket2002-lbosim.streamlit.app/">
    <img alt="Live Demo" src="https://img.shields.io/badge/Demo-Live-%2300c853?logo=streamlit&logoColor=white">
  </a>
  <a href="#license">
    <img alt="License" src="https://img.shields.io/github/license/Aniket2002/lbo-stack">
  </a>
</p>

---

## 1&nbsp;·&nbsp;What is **lbo-stack**?

> **“Excel models break; black-box SaaS hides assumptions.”**  
> `lbo-stack` is an **open, inspectable, and extensible** toolkit that models  
> deal-level cash flows *and* fund-level waterfalls, complete with tests, CI, and a polished UI.

* **Investor-grade accuracy** – cash-sweep hierarchy, LTV & ICR covenants, 100 % GP catch-up, claw-back with interest.  
* **Quant-speed iteration** – vectorised sensitivity grids & bootstrap CIs run orders of magnitude faster than Excel.  
* **Push-button storytelling** – Streamlit front-end exports an investment memo PDF in one click.  
* **Production hygiene** – > 90 % test coverage, GitHub Actions matrix, pre-commit, type hints.

---

## 2&nbsp;·&nbsp;File-tree overview

```
lbo-stack/
├─ .github/workflows/ci.yml        # test + lint matrix
├─ configs/                        # JSON configuration files
├─ data/                          # sample datasets & inputs
├─ docs/
│  ├─ vp_enhancement/             # VP feedback & surgical tweaks
│  └─ templates/                  # report templates
├─ output/
│  ├─ charts/                     # generated PNG charts
│  ├─ reports/                    # generated PDF reports
│  └─ lbo/                        # CSV results & analysis
├─ scripts/                       # utility & generation scripts
├─ src/
│  ├─ modules/
│  │  ├─ cashflow.py
│  │  ├─ exit.py
│  │  ├─ fund_waterfall.py
│  │  ├─ lbo_model.py
│  │  ├─ orchestrator_advanced.py  # VP-enhanced orchestrator
│  │  └─ sensitivity.py
│  └─ utils/                      # helpers, schemas
├─ tests/                         # pytest suite (>90% coverage)
├─ cli.py                         # Typer CLI entrypoint
├─ streamlit_app.py               # Web UI
└─ README.md                      # ← you are here
```

All public APIs live under `src/modules/`; generated outputs go to `output/` to keep root clean.

---

## 3&nbsp;·&nbsp;60-second product tour

| Screenshot | What you see |
|------------|--------------|
| <img src="docs/img/sim.png" width="320"> | **Simulator tab** – tweak leverage, tiers ➜ instant IRR & MOIC |
| <img src="docs/img/compare.png" width="320"> | **Scenario Compare** – benchmark 3 presets side-by-side |
| <img src="docs/img/memo.png" width="320"> | **Memo export** – PDF with narrative, tables & charts |

Live demo 👉 **<https://aniket2002-lbosim.streamlit.app/>**

---

## 4&nbsp;·&nbsp;Quick-Start

```bash
# 1 / Clone and install (editable)
git clone https://github.com/Aniket2002/lbo-stack.git
cd lbo-stack
pip install -e .[ui,dev]

# 2 / Generate sample configs
python cli.py init-sample ./data

# 3 / Run an LBO (7-year horizon)
python cli.py run ./data/sample_lbo.json --years 7 -o ./output -v

# 4 / Launch the Streamlit app
streamlit run streamlit_app.py
````

`--dry-run` validates configs without executing – perfect for CI pipelines.

---

## 5 · Architecture

```mermaid
flowchart LR
  subgraph Engine
    LBO[LBOModel] --> Cash(Cash Sweep)
    Cash --> Exit
    Exit --> Waterfall
  end
  Engine --> Sensitivity
  subgraph Interfaces
    CLI --> Results
    UI --> Memo
  end
  Engine --> CLI
  Engine --> UI
```

Pure-Python, stateless; swap any component with QuantLib, Pandas, etc.

---

## 6 · Road-map

* **v1.1**  Day-weighted simple-pref accrual
* **v1.2**  Rate-grid pricing for TLB + mezz toggle
* **v1.3**  Docker-Compose deploy & Codespaces badge
* **v1.4**  Role-based dashboards (LP vs GP)
* **v2.0**  **Three-Statement Engine** → integrated IS/BS/CF generator feeding the LBO model, enabling working-capital roll-forwards and tax shield precision

*(Open to PRs 👏 – raise an issue if you want to tackle an item.)*

---

## 7 · VP-Enhanced Framework

> **"Finally reads like sponsor material, not student theater."** — PE VP Review

This implementation has been surgically enhanced based on detailed feedback from an active PE VP to achieve **internal-memo-grade** quality:

### Quick Reproduction
```bash
# Generate VP-enhanced analysis with one command
python src/modules/orchestrator_advanced.py

# Output: Enhanced PDF with all VP micro-tweaks
# Result: final_pdf.pdf (659KB) - ship-ready quality
```

### VP Surgical Tweaks Implemented
- **Label Hygiene**: Consistent "Net Debt / EBITDA" format throughout (not "Debt/EBITDA")
- **Sources & Uses Bridge**: Visual micro-graphic showing $1.2B → equity check calculation
- **Exit Equity Bridge**: EBITDA × multiple → EV - net debt - costs = equity value walk
- **Deleveraging Walk**: Year-by-year debt paydown visualization with covenant headroom
- **Monte Carlo Footer**: Explicit priors (±150bps growth, ±200bps margin, ±0.5x multiple)
- **Working Capital**: Days-based approach (DSO/DPO/DIO) vs. % of sales method
- **IFRS-16 Framework**: Lease-in-debt treatment with consistent methodology documentation

### Quality Benchmarks Achieved
- ✅ **Ship-Ready Status**: VP confirmed "wouldn't hold this back"
- ✅ **Internal-Memo-Grade**: Professional labeling and micro-graphics
- ✅ **Recruiter-Ready**: Narrative flows like sponsor material
- ✅ **Technical Rigor**: 9.1% IRR / 1.7x MOIC with proper covenant tracking

### EBITDAR Variant Analysis
See `EBITDAR_APPENDIX.md` for comprehensive comparison of lease treatment approaches:
- Base Case: IFRS-16 lease-in-debt (implemented)
- Alternative: EBITDAR lease-out-of-debt methodology
- Impact Analysis: Multiple and coverage ratio implications

