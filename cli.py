#!/usr/bin/env python3
import json
import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd
import typer
from pydantic import BaseModel, Field, ValidationError

from src.modules.lbo_model import LBOModel
from src.modules.sensitivity import run_sensitivity, export_results
from src.modules.fund_waterfall import compute_waterfall_by_year, summarize_waterfall

app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)


class LBOConfig(BaseModel):
    enterprise_value: float = Field(..., gt=0, description="Total enterprise value")
    debt_pct: float = Field(..., ge=0, le=1, description="Debt % of EV between 0 and 1")
    revenue: float = Field(..., ge=0, description="Initial revenue")
    rev_growth: float = Field(..., gt=-1, lt=5, description="Year-over-year revenue growth rate")
    ebitda_margin: float = Field(..., ge=0, le=1, description="EBITDA margin between 0 and 1")
    capex_pct: float = Field(..., ge=0, le=1, description="CapEx % of revenue")
    wc_pct: float = Field(0.10, ge=0, le=1, description="Working capital % of revenue (default 10%)")
    tax_rate: float = Field(0.25, ge=0, le=1, description="Tax rate between 0 and 1 (default 25%)")
    exit_multiple: float = Field(..., gt=0, description="Exit EBITDA multiple")
    interest_rate: float = Field(..., ge=0, le=1, description="Interest rate between 0 and 1")


class WaterfallConfig(BaseModel):
    committed_capital: float = Field(..., gt=0, description="Total fund committed capital")
    capital_calls: List[float] = Field(..., description="Annual capital calls")
    distributions: List[float] = Field(..., description="Annual distributions")
    tiers: List[dict] = Field(..., description="Waterfall tiers as list of {hurdle, carry}")
    gp_commitment: Optional[float] = Field(0.02, ge=0, le=1, description="GP commitment %")
    mgmt_fee_pct: Optional[float] = Field(0.02, ge=0, le=1, description="Annual management fee %")
    reset_hurdle: Optional[bool] = Field(False, description="Reset hurdle after each tier")
    cashless: Optional[bool] = Field(False, description="Cashless carry mode")


@app.callback(invoke_without_command=True)
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    PE LBO & Fund Waterfall CLI
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)


@app.command()
def run(
    config: Path = typer.Argument(..., exists=True, help="Path to LBO config JSON"),
    output_dir: Path = typer.Option(Path("output/lbo"), "-o", "--output-dir", help="Directory to save LBO results"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate config and exit without running")
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
    typer.secho(f"✅ LBO run complete. Results saved to {out_file}", fg=typer.colors.GREEN)


@app.command()
def waterfall(
    config: Path = typer.Argument(..., exists=True, help="Path to waterfall config JSON"),
    output_dir: Path = typer.Option(Path("output/fund"), "-o", "--output-dir", help="Directory to save waterfall outputs"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate config and exit without running")
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
        typer.secho("✅ Waterfall config is valid. Exiting (dry run).", fg=typer.colors.GREEN)
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)

    breakdown = compute_waterfall_by_year(**cfg.dict())
    summary  = summarize_waterfall(**cfg.dict())

    # Save detailed breakdown
    df     = pd.DataFrame(breakdown)
    csv_out = output_dir / "waterfall_breakdown.csv"
    df.to_csv(csv_out, index=False)

    # Save summary
    json_out = output_dir / "waterfall_summary.json"
    json_out.write_text(json.dumps(summary, indent=2))

    typer.secho(
        f"✅ Waterfall simulation complete.\n"
        f"  Breakdown CSV: {csv_out}\n"
        f"  Summary JSON: {json_out}",
        fg=typer.colors.GREEN
    )


@app.command()
def sensitivity(
    # stub: mimic run/waterfall pattern with config, output-dir, dry-run
):
    """
    Run sensitivity analysis (not yet implemented).
    """
    typer.secho("⚠️ Sensitivity analysis not yet implemented.", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
