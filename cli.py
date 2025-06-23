import sys, os
sys.path.insert(0, os.path.abspath("src"))


import typer
import json
from pathlib import Path
from src.modules.lbo_model import LBOModel
from src.modules.sensitivity import run_sensitivity, export_results, run_2d_sensitivity

app = typer.Typer()

@app.command()
def run(config: Path, years: int = 5):
    """
    Run a single LBO model from JSON config.
    """
    params = json.loads(config.read_text())
    model = LBOModel(**params)
    result = model.run(years)
    for year, data in result.items():
        print(f"\n{year}:")
        for key, val in data.items():
            print(f"  {key}: {val:,.2f}")

@app.command()
def sensitivity(
    config: Path,
    param: str,
    values: str,
    output: Path = Path("output/sensitivity.csv"),
    years: int = 5
):
    """
    Run 1D sensitivity on a single parameter.
    Example: --param exit_multiple --values "6,7,8,9"
    """
    params = json.loads(config.read_text())
    vals = [float(v.strip()) for v in values.split(",")]
    results = run_sensitivity(params, param, vals, years)
    export_results(results, str(output))
    print(f"Saved results to {output}")

@app.command()
def grid(
    config: Path,
    row_param: str,
    row_values: str,
    col_param: str,
    col_values: str,
    metric: str = "IRR",
    output: Path = Path("output/grid.csv"),
    years: int = 5
):
    """
    Run 2D sensitivity grid.
    Example:
    --row-param rev_growth --row-values "0.05,0.10,0.15"
    --col-param exit_multiple --col-values "6,7,8"
    """
    params = json.loads(config.read_text())
    row_vals = [float(v.strip()) for v in row_values.split(",")]
    col_vals = [float(v.strip()) for v in col_values.split(",")]

    df = run_2d_sensitivity(params, row_param, row_vals, col_param, col_vals, years, metric)
    df.to_csv(output)
    print(f"Saved 2D grid to {output}")


if __name__ == "__main__":
    app()
