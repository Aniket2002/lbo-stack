# src/modules/sensitivity.py

import itertools
import time
from typing import Any, Dict, List, Optional

import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.express as px

from src.modules.lbo_model import LBOModel


def run_sensitivity(
    base: Dict[str, Any],
    param: str,
    values: List[float],
    years: int = 5,
    bootstrap: bool = False,
    n_bootstrap: int = 1000,
    ci: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """
    Run 1D sensitivity on a single parameter.

    Returns a list of dicts, each with:
      - "Param": the parameter name
      - "Value": the tested value
      - "IRR": point estimate IRR
      - "MOIC": point estimate MOIC
      - optionally "IRR_CI_Lower" and "IRR_CI_Upper" if bootstrap=True
    """
    if ci is None:
        ci = [2.5, 97.5]

    results: List[Dict[str, Any]] = []
    for v in values:
        cfg = base.copy()
        cfg[param] = v
        model = LBOModel(**cfg)
        run_out = model.run(years)
        summary = run_out["Exit Summary"]
        irr_point = summary["IRR"]
        moic = summary["MOIC"]

        row: Dict[str, Any] = {
            "Param": param,
            "Value": v,
            "IRR": irr_point,
            "MOIC": moic,
        }

        if bootstrap:
            # Build cashflow list for IRR bootstrap
            eq0 = -model.equity
            cashflows = [run_out[f"Year {i}"]["Equity CF"] for i in range(1, years + 1)]
            exit_eq = summary.get("Equity Value", 0.0)
            cf_list = [eq0] + cashflows + [exit_eq]

            boot_irrs: List[float] = []
            for _ in range(n_bootstrap):
                # resample all but the initial outflow
                sample = [cf_list[0]] + list(
                    np.random.choice(cf_list[1:], size=len(cf_list) - 1, replace=True)
                )
                boot_irrs.append(float(npf.irr(sample)))
            lower, upper = np.nanpercentile(boot_irrs, ci)
            row["IRR_CI_Lower"] = float(lower)
            row["IRR_CI_Upper"] = float(upper)

        results.append(row)

    return results


def export_results(data: List[Dict[str, Any]], filename: str) -> None:
    """
    Export a list of result dicts to a CSV file at `filename`.
    """
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)


def results_to_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert a list of result dicts into a pandas DataFrame.
    """
    return pd.DataFrame(results)


def run_2d_sensitivity(
    base: Dict[str, Any],
    param1: str,
    values1: List[float],
    param2: str,
    values2: List[float],
    years: int = 5,
    heatmap: bool = False,
    heatmap_kwargs: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Run 2D sensitivity on two parameters and pivot IRR into a matrix.

    Returns a DataFrame of shape (len(values1), len(values2))
    with index=values1, columns=values2.

    If heatmap=True, displays an interactive heatmap via plotly.express.imshow.
    As a performance guard, asserts runtime < 1s for a 100×100 grid.
    """
    start = time.time()

    # Collect (summary, v1, v2) tuples without using a walrus assignment
    rows: List[tuple] = []
    for v1, v2 in itertools.product(values1, values2):
        cfg = {**base, param1: v1, param2: v2}
        summary = LBOModel(**cfg).run(years)["Exit Summary"]
        rows.append((summary, v1, v2))

    # Build DataFrame
    data = [
        {param1: v1, param2: v2, "IRR": summary["IRR"], "MOIC": summary["MOIC"]}
        for summary, v1, v2 in rows
    ]
    df = pd.DataFrame(data)
    pivot = df.pivot(index=param1, columns=param2, values="IRR")

    # Optional heatmap
    if heatmap:
        fig = px.imshow(
            pivot.values,
            x=pivot.columns,
            y=pivot.index,
            labels={"x": param2, "y": param1, "color": "IRR"},
            **(heatmap_kwargs or {}),
        )
        fig.show()

    # Performance guard for large grids
    if len(values1) * len(values2) >= 10_000:
        duration = time.time() - start
        assert duration < 1.0, f"run_2d_sensitivity too slow: {duration:.3f}s"

    return pivot
