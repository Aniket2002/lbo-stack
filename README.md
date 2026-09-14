# LBO Stack

An applied leveraged-finance toolkit for transparent annual LBO scenario analysis.

LBO Stack turns a declared set of transaction and operating assumptions into a
reconciled sources-and-uses schedule, debt and cash roll-forward, covenant view,
exit-equity bridge, sponsor returns, sensitivities, and scenario analysis. It is
designed to make the mechanics inspectable rather than hide them behind a
spreadsheet.

This repository is the practical transaction-modelling project in the portfolio.
The separate [IFRS 16 LBO Engine](https://github.com/Aniket2002/ifrs16-lbo-engine)
focuses on model validation and threshold portability in a synthetic research
benchmark.

## Highlights

- Senior, mezzanine, bullet, revolver, and simplified IFRS 16 debt tranches.
- Separate cash and PIK interest, mandatory amortisation, and optional cash sweeps.
- Minimum-cash funding, revolver draws, and explicit cash/debt reconciliation.
- Net-debt leverage, cash-interest coverage, and cash-flow coverage.
- Operating and exit sensitivities plus seeded, assumption-driven Monte Carlo paths.
- A single-tier European-style fund waterfall, Streamlit interface, and PDF summary.

## Workflow

```text
deal assumptions
  -> sources and uses
  -> annual operating projection
  -> cash / debt / revolver waterfall
  -> covenants and sensitivities
  -> exit equity and sponsor returns
  -> fund-level distribution waterfall
```

## Quick start

Python 3.10-3.12 is exercised in CI.

```bash
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -r requirements.txt
python -m src.modules.orchestrator_advanced
```

The command reads the included illustrative Accor assumptions and writes
`output/lbo_analysis.pdf`. Generated output is ignored so that a local run does
not change the repository.

Launch the interactive model with:

```bash
streamlit run src/modules/streamlit_app.py
```

## Model scope

The annual engine includes:

- transaction sources and uses;
- operating projections, capex, working capital, and simplified cash taxes;
- an annual NOL roll-forward;
- minimum-cash funding and revolver capacity;
- priority-ordered amortisation and cash sweeps;
- covenant monitoring and explicit failure states;
- exit-equity and sponsor-return reconciliation;
- operating/exit sensitivities and seeded scenario analysis.

The dashboard calls the same modelling functions used by the command-line workflow;
it is a presentation layer rather than a separate engine.

## Core reconciliation formulas

### Cash

```text
Closing cash
= Opening cash
+ Operating cash generation
+ Operating revolver draw
- Cash-funded mandatory amortisation
- Optional cash sweep
```

Revolver-funded mandatory amortisation does not pass through ending cash: the draw
increases revolver debt and immediately repays the target debt tranche.

### Debt

```text
Closing debt
= Opening debt
+ Revolver draws
+ PIK interest
- Actual mandatory amortisation
- Optional cash sweep
```

### Exit equity

```text
Exit equity
= Exit enterprise value
- Sale costs
- Closing debt
+ Closing cash
```

The opening sponsor cash flow equals the equity cheque from the canonical
sources-and-uses schedule. Transaction fees, financing fees, OID, and retained cash
therefore enter sponsor returns directly.

## Waterfall convention

The current waterfall supports one European-style whole-fund tier:

1. pro-rata return of LP and GP contributed capital;
2. compounded LP preferred return;
3. 100% GP catch-up;
4. residual LP/GP split;
5. optional cashless carry deferral;
6. an end-of-life clawback check.

Management fees are separate investor cash outflows and are not deducted from
portfolio distributions. Cash distributions and LP/GP cash flows include the final
clawback transfer. In cashless mode, carry is held in a simplified notional reserve
until the final model period. Multi-tier waterfalls and hurdle resets deliberately
raise `NotImplementedError`.

## Monte Carlo reporting

The Monte Carlo inputs are uncalibrated scenario assumptions. Percentiles include
every completed path with a mathematically defined IRR, including underperforming
paths. Model failures, insolvencies, and undefined IRRs are reported separately;
they are not replaced with an arbitrary return. Unconditional statistics are shown
only when every simulated path has a defined IRR.

## Validation

```bash
python -m pytest -q
python -m pytest -q --cov=src/modules --cov-report=term-missing --cov-fail-under=75
python -m ruff check src tests
```

Deterministic tests cover sources-and-uses equality, cash and debt roll-forwards,
minimum cash, revolver capacity, covenant failures, exit-equity reconciliation,
IRR cash flows, and fund-waterfall allocation.

## Data and reproducibility

`data/accor_assumptions.csv` and `data/accor_historical_recreated.csv` are
illustrative reconstructed inputs, not audited company or transaction data. The
base workflow and Monte Carlo generator use fixed seeds where randomness is
involved. Results still depend on the declared assumptions and installed numerical
libraries.

## Limitations

- The model is annual, not monthly or quarterly.
- Tax, interest deductibility, and NOL treatment are simplified and not
  jurisdiction-specific.
- IFRS 16 treatment is assumption-driven, not a complete lease-accounting engine.
- Lease principal follows an assumed amortisation period.
- Monte Carlo distributions are scenarios, not empirically calibrated forecasts.
- The fund waterfall is simplified and does not replace an LPA-specific legal model.
- Multi-tier waterfalls, detailed refinancing, and intra-period liquidity are not
  supported.

## Repository structure

```text
src/modules/lbo_model.py             annual cash and debt engine
src/modules/orchestrator_advanced.py transaction workflow, sensitivities, reports
src/modules/fund_waterfall.py        fund distribution mechanics
src/modules/streamlit_app.py         interactive presentation layer
tests/                               deterministic financial invariants
data/                                illustrative reconstructed inputs
output/                              ignored local reports
```

## License and disclaimer

[MIT licensed](LICENSE). This project is for education and scenario analysis; it is
not investment advice, a valuation opinion, or a substitute for transaction,
accounting, tax, or legal diligence.
