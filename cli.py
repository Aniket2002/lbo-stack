#!/usr/bin/env python3
import json
import logging
from pathlib import Path

import pandas as pd
import typer
from pydantic import BaseModel, Field, ValidationError

from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall
from src.modules.lbo_model import LBOModel
from src.modules.sensitivity import (
    results_to_dataframe,
    run_2d_sensitivity,
    run_sensitivity,
)

app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)

# ─── CLI Defaults (avoid B008) ──────────────────────────────────────────

DEFAULT_CONFIGS_DIR = Path("configs")
DEFAULT_LBO_OUT = Path("output/lbo")
DEFAULT_FUNDS_OUT = Path("output/fund")
DEFAULT_SENS_OUT = Path("output/sensitivity")

RUN_CONFIG_ARG = typer.Argument(..., exists=True, help="Path to LBO config JSON")
WF_CONFIG_ARG = typer.Argument(..., exists=True, help="Path to waterfall config JSON")
SENS_CONFIG_ARG = typer.Argument(
    ..., exists=True, help="Path to sensitivity config JSON"
)

VERBOSE_OPT = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")

INIT_SAMPLE_OUT_OPT = typer.Option(
    DEFAULT_CONFIGS_DIR, "--out-dir", "-d", help="Where to write sample configs"
)

RUN_OUT_OPT = typer.Option(
    DEFAULT_LBO_OUT, "-o", "--output-dir", help="Directory to save LBO results"
)
RUN_DRY_OPT = typer.Option(False, "--dry-run", help="Validate config and exit")
RUN_YEARS_OPT = typer.Option(5, "--years", help="Projection horizon")
RUN_EXTRA_OPT = typer.Option(
    "{}", "--extra-params", help="JSON for extra LBOModel kwargs"
)

WF_OUT_OPT = typer.Option(
    DEFAULT_FUNDS_OUT, "-o", "--output-dir", help="Directory to save waterfall outputs"
)
WF_DRY_OPT = typer.Option(False, "--dry-run", help="Validate config and exit")
WF_YEARS_OPT = typer.Option(None, "--years", help="Horizon for waterfall (pads zeros)")
WF_EXTRA_OPT = typer.Option(
    "{}", "--extra-params", help="JSON for extra compute kwargs"
)

SENS_OUT_OPT = typer.Option(
    DEFAULT_SENS_OUT, "-o", "--output-dir", help="Directory to save sensitivity outputs"
)
SENS_DRY_OPT = typer.Option(False, "--dry-run", help="Validate config and exit")
SENS_EXTRA_OPT = typer.Option(
    "{}", "--extra-params", help="JSON for run_sensitivity kwargs"
)


# ─── Pydantic Models ────────────────────────────────────────────────────


class LBOConfig(BaseModel):
    enterprise_value: float = Field(..., gt=0, description="Total enterprise value")
    debt_pct: float = Field(..., ge=0, le=1, description="Debt % of EV")
    revenue: float = Field(..., ge=0, description="Initial revenue")
    rev_growth: float = Field(..., gt=-1, lt=5, description="YOY revenue growth")
    ebitda_margin: float = Field(..., ge=0, le=1, description="EBITDA margin")
    capex_pct: float = Field(..., ge=0, le=1, description="CapEx % of revenue")
    wc_pct: float = Field(0.10, ge=0, le=1, description="WC % of revenue")
    tax_rate: float = Field(0.25, ge=0, le=1, description="Tax rate")
    exit_multiple: float = Field(..., gt=0, description="Exit EBITDA multiple")
    interest_rate: float = Field(..., ge=0, le=1, description="Interest rate")


class WaterfallConfig(BaseModel):
    committed_capital: float = Field(..., gt=0, description="Total committed capital")
    capital_calls: list[float] = Field(..., description="Annual capital calls")
    distributions: list[float] = Field(..., description="Annual distributions")
    tiers: list[dict] = Field(..., description="Waterfall tiers")
    gp_commitment: float = Field(0.02, ge=0, le=1, description="GP commitment %")
    mgmt_fee_pct: float = Field(0.02, ge=0, le=1, description="Management fee %")
    reset_hurdle: bool = Field(False, description="Reset hurdle each tier")
    cashless: bool = Field(False, description="Cashless carry mode")


# ─── Entrypoint ─────────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def main(verbose: bool = VERBOSE_OPT):
    """
    PE LBO & Fund Waterfall CLI
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)
    logger.setLevel(level)


# ─── init-sample ────────────────────────────────────────────────────────


@app.command("init-sample")
def init_sample(out_dir: Path = INIT_SAMPLE_OUT_OPT):
    """
    Write sample JSON configs for run, waterfall, sensitivity.
    """
    samples = {
        "lbo_sample.json": {
            "enterprise_value": 100.0,
            "debt_pct": 0.6,
            "revenue": 50.0,
            "rev_growth": 0.1,
            "ebitda_margin": 0.2,
            "capex_pct": 0.05,
            "wc_pct": 0.1,
            "tax_rate": 0.25,
            "exit_multiple": 8.0,
            "interest_rate": 0.07,
            "years": 5,
        },
        "waterfall_sample.json": {
            "committed_capital": 100.0,
            "capital_calls": [20, 20, 20, 20, 20],
            "distributions": [0, 0, 0, 0, 150],
            "tiers": [{"hurdle": 0.08, "carry": 0.2}],
            "gp_commitment": 0.02,
            "mgmt_fee_pct": 0.02,
            "reset_hurdle": False,
            "cashless": False,
        },
        "sensitivity_sample.json": {
            "base": {
                "enterprise_value": 100.0,
                "debt_pct": 0.6,
                "revenue": 50.0,
                "rev_growth": 0.1,
                "ebitda_margin": 0.2,
                "capex_pct": 0.05,
                "wc_pct": 0.1,
                "tax_rate": 0.25,
                "exit_multiple": 8.0,
                "interest_rate": 0.07,
            },
            "param": "exit_multiple",
            "values": [6.0, 8.0, 10.0],
            "years": 5,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for fname, cfg in samples.items():
        p = out_dir / fname
        p.write_text(json.dumps(cfg, indent=2))
        typer.secho(f"Created {p}", fg=typer.colors.GREEN)


# ─── run ────────────────────────────────────────────────────────────────


@app.command("run")
def run(
    config: Path = RUN_CONFIG_ARG,
    output_dir: Path = RUN_OUT_OPT,
    dry_run: bool = RUN_DRY_OPT,
    years: int = RUN_YEARS_OPT,
    extra_params: str = RUN_EXTRA_OPT,
):
    """
    Run the LBO model using a JSON config.
    """
    logger.info("Starting LBO run: %s", config)
    try:
        raw = json.loads(config.read_text())
        cfg = LBOConfig(**raw)
    except (json.JSONDecodeError, ValidationError) as e:
        typer.secho(f"❌ Configuration error:\n{e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if dry_run:
        typer.secho("✅ Configuration valid (dry run)", fg=typer.colors.GREEN)
        raise typer.Exit()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        typer.secho(f"❌ Cannot create output dir: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    try:
        extras = json.loads(extra_params)
        assert isinstance(extras, dict)
    except Exception:
        typer.secho("❌ --extra-params must be a JSON object", fg=typer.colors.RED)
        raise typer.Exit(1)

    invalid = set(extras) - set(cfg.dict())
    if invalid:
        typer.secho(
            f"⚠️ Ignored extra-params keys: {', '.join(invalid)}",
            fg=typer.colors.YELLOW,
        )

    model = LBOModel(
        **cfg.dict(), **{k: v for k, v in extras.items() if k in cfg.dict()}
    )
    results = model.run(years=years)

    out_file = output_dir / "lbo_results.json"
    logger.info("Writing LBO results to %s", out_file)
    try:
        out_file.write_text(json.dumps(results, indent=2))
    except OSError as e:
        typer.secho(f"❌ Failed to write results: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    es = results["Exit Summary"]
    typer.secho("✅ LBO run complete", fg=typer.colors.GREEN)
    typer.echo(f"  Exit Year : {es['Exit Year']}")
    typer.echo(f"  Equity    : ${es['Equity Value']:,}")
    typer.echo(
        f"  {typer.style('IRR:', fg=typer.colors.GREEN, bold=True)} {es['IRR']:.2%}"
    )
    typer.echo(
        f"  {typer.style('MOIC:', fg=typer.colors.GREEN, bold=True)} {es['MOIC']:.2f}x"
    )


# ─── waterfall ────────────────────────────────────────────────────────


@app.command("waterfall")
def waterfall(
    config: Path = WF_CONFIG_ARG,
    output_dir: Path = WF_OUT_OPT,
    dry_run: bool = WF_DRY_OPT,
    years: int = WF_YEARS_OPT,
    extra_params: str = WF_EXTRA_OPT,
):
    """
    Run fund waterfall simulation using a JSON config.
    """
    logger.info("Starting waterfall run: %s", config)
    try:
        raw = json.loads(config.read_text())
        cfg = WaterfallConfig(**raw)
    except (json.JSONDecodeError, ValidationError) as e:
        typer.secho(f"❌ Configuration error:\n{e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if dry_run:
        typer.secho("✅ Configuration valid (dry run)", fg=typer.colors.GREEN)
        raise typer.Exit()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        typer.secho(f"❌ Cannot create output dir: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    try:
        extras = json.loads(extra_params)
        assert isinstance(extras, dict)
    except Exception:
        typer.secho("❌ --extra-params must be a JSON object", fg=typer.colors.RED)
        raise typer.Exit(1)

    invalid = set(extras) - set(cfg.dict())
    if invalid:
        typer.secho(
            f"⚠️ Ignored extra-params keys: {', '.join(invalid)}",
            fg=typer.colors.YELLOW,
        )

    calls = cfg.capital_calls.copy()
    dists = cfg.distributions.copy()
    if years is not None and years > len(calls):
        calls += [0.0] * (years - len(calls))
        dists += [0.0] * (years - len(dists))

    logger.info("Computing waterfall for %d years", len(calls))
    breakdown = compute_waterfall_by_year(
        cfg.committed_capital,
        calls,
        dists,
        **{k: v for k, v in extras.items() if k in cfg.dict()},
    )
    summary = summarize_waterfall(
        cfg.committed_capital,
        calls,
        dists,
        **{k: v for k, v in extras.items() if k in cfg.dict()},
    )

    csv_out = output_dir / "breakdown.csv"
    json_out = output_dir / "summary.json"

    logger.info("Writing breakdown to %s", csv_out)
    try:
        pd.DataFrame(breakdown).to_csv(csv_out, index=False)
    except OSError as e:
        typer.secho(f"❌ Failed to write CSV: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    logger.info("Writing summary to %s", json_out)
    try:
        json_out.write_text(json.dumps(summary, indent=2))
    except OSError as e:
        typer.secho(f"❌ Failed to write summary: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    typer.secho("✅ Waterfall complete", fg=typer.colors.GREEN)
    typer.echo(f"  Net LP IRR : {summary['Net IRR (LP)']:.2%}")
    typer.echo(f"  MOIC       : {summary['MOIC']:.2f}x")
    typer.echo(f"  GP Carry   : {summary['Cumulative GP Carry']:.2f}")


# ─── sensitivity ──────────────────────────────────────────────────────


@app.command("sensitivity")
def sensitivity(
    config: Path = SENS_CONFIG_ARG,
    output_dir: Path = SENS_OUT_OPT,
    dry_run: bool = SENS_DRY_OPT,
    extra_params: str = SENS_EXTRA_OPT,
):
    """
    Run 1D or 2D sensitivity analysis based on JSON config.
    """
    logger.info("Starting sensitivity run: %s", config)
    try:
        cfg = json.loads(config.read_text())
        base = cfg["base"]
        p1, v1 = cfg["param"], cfg["values"]
        p2, v2 = cfg.get("param2"), cfg.get("values2")
        years = cfg.get("years", 5)
    except Exception as e:
        typer.secho(f"❌ Invalid sensitivity config: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if dry_run:
        typer.secho("✅ Configuration valid (dry run)", fg=typer.colors.GREEN)
        raise typer.Exit()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        typer.secho(f"❌ Cannot create output dir: {e}", fg=typer.colors.RED)
        raise typer.Exit(2)

    try:
        extras = json.loads(extra_params)
        assert isinstance(extras, dict)
    except Exception:
        typer.secho("❌ --extra-params must be a JSON object", fg=typer.colors.RED)
        raise typer.Exit(1)

    invalid = set(extras) - {
        "bootstrap",
        "n_bootstrap",
        "ci",
        "heatmap",
        "heatmap_kwargs",
    }
    if invalid:
        typer.secho(
            f"⚠️ Ignored extra-params keys: {', '.join(invalid)}",
            fg=typer.colors.YELLOW,
        )

    if p2 and v2:
        df2 = run_2d_sensitivity(base, p1, v1, p2, v2, **extras, years=years)
        out = output_dir / "sensitivity_2d.csv"
        logger.info("Writing 2D sensitivity to %s", out)
        try:
            df2.to_csv(out, index=False)
        except OSError as e:
            typer.secho(f"❌ Failed to write 2D CSV: {e}", fg=typer.colors.RED)
            raise typer.Exit(2)
        typer.secho(f"✅ 2D sensitivity saved to {out}", fg=typer.colors.GREEN)
    else:
        results = run_sensitivity(base, p1, v1, **extras, years=years)
        df1 = results_to_dataframe(results)
        out = output_dir / "sensitivity_1d.csv"
        logger.info("Writing 1D sensitivity to %s", out)
        try:
            df1.to_csv(out, index=False)
        except OSError as e:
            typer.secho(f"❌ Failed to write 1D CSV: {e}", fg=typer.colors.RED)
            raise typer.Exit(2)
        typer.secho(f"✅ 1D sensitivity saved to {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
