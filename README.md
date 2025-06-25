````markdown
<h1 align="center">
  LBO & Fund Waterfall Simulator 🦄
</h1>

<p align="center">
  <em>Deal-grade analytics &nbsp;|&nbsp; Partner-grade transparency &nbsp;|&nbsp; Push-button storytelling</em>
</p>

<p align="center">
  <a href="https://github.com/Aniket2002/lbo-stack/actions/workflows/ci.yml">
    <img alt="CI Status" src="https://img.shields.io/github/actions/workflow/status/Aniket2002/lbo-stack/ci.yml?label=CI&logo=github">
  </a>
  <a href="https://codecov.io/gh/Aniket2002/lbo-stack">
    <img alt="Coverage" src="https://img.shields.io/codecov/c/github/Aniket2002/lbo-stack?logo=codecov">
  </a>
  <a href="https://pypi.org/project/lbo-stack/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/lbo-stack?logo=pypi&color=blue">
  </a>
  <a href="#license">
    <img alt="License" src="https://img.shields.io/github/license/Aniket2002/lbo-stack">
  </a>
  <a href="https://lbo-demo.streamlit.app">
    <img alt="Live Demo" src="https://img.shields.io/badge/Demo-Live-%2300c853?logo=streamlit&logoColor=white">
  </a>
</p>

---

## 1. Why ‟lbo-stack” matters
> **“Excel macros don’t scale and black-box SaaS tools miss the nuance.”**  
> lbo-stack gives investment teams an **open, inspectable, and extensible** engine for modelling  
> deal-level cashflows **and** fund-level economics—complete with CI/CD, test coverage, and a polished UI.

* **Investor-grade accuracy**  
  *Cash-sweep hierarchy, LTV & ICR covenants, day-one fees, 100 % GP catch-up, claw-back with interest.*
* **Quant-speed iteration**  
  *Vectorised sensitivities & bootstrap CIs run 100× faster than Excel grids.*
* **Push-button storytelling**  
  *Streamlit front-end exports an investment memo PDF in one click.*
* **Battle-tested quality**  
  *>90 % unit-test coverage, GitHub Actions matrix (3.9-3.12), pre-commit lint, type-hints.*

---

## 2. Tour-in-60-seconds

| Screenshot | What you see |
|------------|--------------|
| <img src="docs/img/sim.png" width="320"> | **Simulator tab** – tweak leverage, growth, tiers ➜ instant IRR/MOIC & GP/LP chart |
| <img src="docs/img/compare.png" width="320"> | **Scenario Compare** – preset cases benchmarked side-by-side |
| <img src="docs/img/memo.png" width="320"> | **Memo export** – PDF with tables, charts, narrative & assumptions |

*(Live demo ⤴︎ link at top – no sign-up required).*

---

## 3. Quick-Start

```bash
# 1 / Install
pip install lbo-stack[ui]  # pulls Streamlit, Plotly, WeasyPrint

# 2 / Generate sample configs
lbo init-sample ./configs

# 3 / Run an LBO
lbo run ./configs/sample_lbo.json -y 7 -o ./results --verbose

# 4 / Open the UI
streamlit run -m lbo_stack.streamlit_app
````

> **CI-proof:** `lbo run … --dry-run` validates config without executing simulations—perfect for PR gates.

---

## 4. Architecture at a glance

```mermaid
flowchart LR
    subgraph Engine
      LBO[LBOModel] --> Cash(Cash-Sweep & Covenants)
      Cash --> Exit[Exit Maths]
      Exit --> Waterfall(Fund Waterfall)
    end
    Engine --> Sensitivity(Sensitivity Grid + Bootstrap CI)
    subgraph Interfaces
      CLI -->|json/csv| Results
      UI --> Memo
    end
    Engine --> CLI
    Engine --> UI
    Engine --> Tests
```

*Pure Python, stateless; any step can be swapped for QuantLib, PyTorch, etc.*

---

## 5. Feature deep-dive

| Layer                | Highlights                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Deal Engine**      | • Bullet & amort tranches with rate grids<br>• Revolver draw/repay<br>• Cash-sweep cascading senior→junior→PIK<br>• LTV & ICR breach errors |
| **Fund Waterfall**   | • Ascending hurdles (IRR or simple pref)<br>• 100 % catch-up<br>• LP capital-return gate<br>• Claw-back with simple interest                |
| **Analysis Toolkit** | • 1-D / 2-D sensitivity (`exit_multiple`, leverage, growth …)<br>• Bootstrap IRR confidence intervals<br>• Plotly heat-map export           |
| **CLI**              | • `init-sample`, `run`, `waterfall`, `sensitivity` sub-commands<br>• JSON extras passthrough & colourised KPI printout                      |
| **Streamlit UI**     | • Three-tab workflow<br>• Drag-and-drop tier editor<br>• Colour-coded KPIs<br>• One-click Markdown→PDF memos                                |

---

## 6. Benchmarks

| Scenario grid                          | Runtime (M1 Pro) |
| -------------------------------------- | ---------------- |
| 50 × 50 → 2 500 sims                   | **0.6 s**        |
| 100 × 100 → 10 000 sims (parallel = 4) | **1.8 s**        |
| Bootstrap 1 000 draws, 7-yr CF         | **0.9 s**        |

> **Fast enough to plug into a Friday IC pack on the fly.**

---

<!-- ## 7. Research pedigree

Portions of lbo-stack underpin my forthcoming paper:

> **“Quantifying the Impact of Fund-Waterfall Design on GP/LP Outcomes”**
> (pre-print DOI 10.48550/arXiv.NNNNN)

All figures in the manuscript are reproducible via `notebooks/paper_figures.ipynb`.

--- -->

## 8. Road-map (v1.1 → v2.0)

* [ ] Day-weighted simple pref accrual
* [ ] Rate-grid pricing on Term-Loan B
* [ ] Monte-Carlo portfolio wrapper
* [ ] Role-based dashboards (LP vs GP)
* [ ] Docker-compose one-liner deploy

*Issues & PRs welcome — let’s build the Bloomberg-Terminal of private equity.*

---

## License

MIT — free to use, fork, and improve. Just throw a ⭐ if it saves your Monday.

```
```
