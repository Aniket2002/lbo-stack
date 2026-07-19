# LBO Stack

An educational Python toolkit for annual LBO scenario analysis with explicit cash, debt, revolver, covenant and exit-equity reconciliation.

## Model scope

The repository includes:

- transaction sources and uses;
- senior, mezzanine, bullet, revolver and simplified IFRS-16 debt;
- separate cash and PIK interest;
- cash taxes with a simplified NOL roll-forward;
- minimum-cash funding and revolver draws;
- mandatory amortisation and optional cash sweeps;
- cash and debt roll-forward checks;
- net-debt leverage, cash-interest coverage and cash-flow coverage;
- exit-equity and sponsor-return reconciliation;
- operating and exit sensitivities;
- unconditional Monte Carlo scenario statistics;
- a single-tier European-style fund waterfall;
- a Streamlit dashboard and PDF summary.

## Installation

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
pip install -r requirements.txt
```

## Run the model

From the repository root:

```bash
python -m src.modules.orchestrator_advanced
```

Generated files are written to `output/`.

## Run the dashboard

```bash
streamlit run src/modules/streamlit_app.py
```

## Run tests

```bash
python -m pytest -q
```

Run the same coverage gate used by CI:

```bash
python -m pytest -q \
  --cov=src/modules \
  --cov-report=term-missing \
  --cov-fail-under=65
```

Run linting:

```bash
python -m ruff check src tests
```

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

Revolver-funded mandatory amortisation does not pass through ending cash: the draw increases revolver debt and immediately repays the target debt tranche.

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

### Initial sponsor investment

The opening equity cash flow equals the sponsor-equity cheque from the canonical sources-and-uses schedule. Transaction fees, financing fees, OID and retained cash therefore enter sponsor returns directly.

## Waterfall convention

The current waterfall supports one European-style whole-fund tier with:

1. pro-rata return of LP and GP contributed capital;
2. compounded LP preferred return;
3. 100% GP catch-up;
4. residual LP/GP split;
5. optional cashless carry deferral;
6. end-of-life clawback check.

Management fees are treated as separate investor cash outflows and are not deducted from portfolio distributions.

Multi-tier waterfalls and hurdle resets deliberately raise `NotImplementedError` rather than presenting unsupported economics.

## Limitations

- The model is annual, not monthly or quarterly.
- Tax, interest deductibility and NOL treatment are simplified.
- The IFRS-16 module is assumption-driven and does not reproduce a full lease-accounting schedule.
- Lease principal is modelled through an assumed amortisation period.
- The included Accor inputs are illustrative reconstructed assumptions, not audited transaction data.
- Monte Carlo priors are scenario assumptions, not empirically calibrated forecasts.
- The fund waterfall is simplified and does not replace an LPA-specific legal model.
- Multi-tier waterfalls are not supported.

## Suggested project description

> Developed a Python LBO scenario-analysis toolkit with multi-tranche debt, minimum-cash and revolver mechanics, covenant monitoring, operating sensitivities and Monte Carlo stress testing.

## Repository structure

```text
lbo-stack/
├── src/
│   └── modules/
│       ├── lbo_model.py
│       ├── fund_waterfall.py
│       ├── orchestrator_advanced.py
│       └── streamlit_app.py
├── tests/
│   ├── test_invariants.py
│   └── test_fund_waterfall.py
├── data/
├── output/
├── requirements.txt
├── pyproject.toml
└── README.md
```

## License

MIT
