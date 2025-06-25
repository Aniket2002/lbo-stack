#!/usr/bin/env python3
import json
import logging
from pathlib import Path
from typing import List, Optional

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


# ─── Typer argument & option defaults ──────────────────────────────────

VERBOSE = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")

RUN_CONFIG = typer.Argument(..., exists=True, help="Path to LBO config JSON")
RUN_OUTPUT = typer.Option(
    Path("output/lbo"),
    "-o",
    "--output-dir",
    help="Directory to save LBO results",
)
RUN_DRY = typer.Option(
    False, "--dry-run", help="Validate config and exit without running"
)

WF_CONFIG = typer.Argument(..., exists=True, help="Path to waterfall config JSON")
WF_OUTPUT = typer.Option(
    Path("output/fund"),
    "-o",
    "--output-dir",
    help="Directory to save waterfall outputs",
)
WF_DRY = typer.Option(
    False, "--dry-run", help="Validate config and exit without running"
)

SENS_CONFIG = typer.Argument(..., help="Path to sensitivity config JSON")
SENS_OUTPUT = typer.Option(
    Path("output/sensitivity"),
    "-o",
    "--output-dir",
    help="Directory to save sensitivity outputs",
)
SENS_DRY = typer.Option(False, "--dry-run", help="Validate config and exit (dry run)")


# ─── Pydantic configuration models ────────────────────────────────────


class LBOConfig(BaseModel):
    enterprise_value: float = Field(..., gt=0, description="Total enterprise value")
    debt_pct: float = Field(..., ge=0, le=1, description="Debt % of EV between 0 and 1")
    revenue: float = Field(..., ge=0, description="Initial revenue")
    rev_growth: float = Field(
        ..., gt=-1, lt=5, description="Year-over-year revenue growth rate"
    )
    ebitda_margin: float = Field(
        ..., ge=0, le=1, description="EBITDA margin between 0 and 1"
    )
    capex_pct: float = Field(..., ge=0, le=1, description="CapEx % of revenue")
    wc_pct: float = Field(
        0.10, ge=0, le=1, description="Working capital % of revenue (default 10%)"
    )
    tax_rate: float = Field(
        0.25, ge=0, le=1, description="Tax rate between 0 and 1 (default 25%)"
    )
    exit_multiple: float = Field(..., gt=0, description="Exit EBITDA multiple")
    interest_rate: float = Field(
        ..., ge=0, le=1, description="Interest rate between 0 and 1"
    )


class WaterfallConfig(BaseModel):
    committed_capital: float = Field(
        ..., gt=0, description="Total fund committed capital"
    )
    capital_calls: List[float] = Field(..., description="Annual capital calls")
    distributions: List[float] = Field(..., description="Annual distributions")
    tiers: List[dict] = Field(
        ..., description="Waterfall tiers as list of {hurdle, carry}"
    )
    gp_commitment: Optional[float] = Field(
        0.02, ge=0, le=1, description="GP commitment %"
    )
    mgmt_fee_pct: Optional[float] = Field(
        0.02, ge=0, le=1, description="Annual management fee %"
    )
    reset_hurdle: Optional[bool] = Field(
        False, description="Reset hurdle after each tier"
    )
    cashless: Optional[bool] = Field(False, description="Cashless carry mode")


# ─── CLI entrypoint & commands ────────────────────────────────────────


@app.callback(invoke_without_command=True)
def main(verbose: bool = VERBOSE):
    """
    PE LBO & Fund Waterfall CLI
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)


@app.command()
def run(
    config: Path = RUN_CONFIG,
    output_dir: Path = RUN_OUTPUT,
    dry_run: bool = RUN_DRY,
):
    """
    Run the LBO model using a JSON config.
    """
    try:
        raw = json.loads(config.read_text())
        cfg = LBOConfig(**raw)
        logger.debug("Loaded LBO config: %s", cfg.json())
    except (json.JSONDecodeError, ValidationError) as e:
        typer.secho(f"❌ Configuration error:\n{e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if dry_run:
        typer.secho("✅ LBO config is valid. Exiting (dry run).", fg=typer.colors.GREEN)
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)
    model = LBOModel(**cfg.dict())
    result = model.run(years=raw.get("years", 5))

    out_file = output_dir / "lbo_results.json"
    out_file.write_text(json.dumps(result, indent=2))
    typer.secho(
        f"✅ LBO run complete. Results saved to {out_file}", fg=typer.colors.GREEN
    )


@app.command()
def waterfall(
    config: Path = WF_CONFIG,
    output_dir: Path = WF_OUTPUT,
    dry_run: bool = WF_DRY,
):
    """
    Run fund waterfall simulation using a JSON config.
    """
    try:
        raw = json.loads(config.read_text())
        cfg = WaterfallConfig(**raw)
        logger.debug("Loaded Waterfall config: %s", cfg.json())
    except (json.JSONDecodeError, ValidationError) as e:
        typer.secho(f"❌ Configuration error:\n{e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if dry_run:
        typer.secho(
            "✅ Waterfall config is valid. Exiting (dry run).", fg=typer.colors.GREEN
        )
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)
    breakdown = compute_waterfall_by_year(**cfg.dict())
    summary = summarize_waterfall(**cfg.dict())

    # Save detailed breakdown
    df = pd.DataFrame(breakdown)
    csv_out = output_dir / "waterfall_breakdown.csv"
    df.to_csv(csv_out, index=False)

    # Save summary
    json_out = output_dir / "waterfall_summary.json"
    json_out.write_text(json.dumps(summary, indent=2))

    typer.secho(
        f"✅ Waterfall simulation complete.\n"
        f"  Breakdown CSV: {csv_out}\n"
        f"  Summary JSON: {json_out}",
        fg=typer.colors.GREEN,
    )


@app.command()
def sensitivity(
    config: Path = SENS_CONFIG,
    output_dir: Path = SENS_OUTPUT,
    dry_run: bool = SENS_DRY,
):
    """
    Run 1D or 2D sensitivity analysis based on JSON config.
    """
    try:
        cfg = json.loads(config.read_text())
        base = cfg["base"]
        p1 = cfg["param"]
        v1 = cfg["values"]
        p2 = cfg.get("param2")
        v2 = cfg.get("values2")
        years = cfg.get("years", 5)
    except Exception as e:
        typer.secho(f"❌ Invalid sensitivity config: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if dry_run:
        typer.secho(
            "✅ Sensitivity config valid. Exiting (dry run).", fg=typer.colors.GREEN
        )
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)
    if p2 and v2:
        df2 = run_2d_sensitivity(base, p1, v1, p2, v2, years=years)
        out = output_dir / "sensitivity_2d.csv"
        df2.to_csv(out, index=False)
        typer.secho(f"✅ 2D sensitivity saved to {out}", fg=typer.colors.GREEN)
    else:
        results = run_sensitivity(base, p1, v1, years=years)
        df1 = results_to_dataframe(results)
        out = output_dir / "sensitivity_1d.csv"
        df1.to_csv(out, index=False)
        typer.secho(f"✅ 1D sensitivity saved to {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
