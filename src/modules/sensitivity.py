import itertools
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.express as px

from src.modules.lbo_model import LBOModel


def _bootstrap_irr(
    cf_list: List[float], n_bootstrap: int, ci: List[float]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Perform bootstrap CI on IRR by resampling cashflow indices to preserve order.
    Returns (lower, upper) or (None, None) if not enough valid draws.
    """
    boot_irrs: List[float] = []
    # Cashflow list looks like [t0, t1, t2, ..., tN, t_exit]
    # we resample positions 1..N (len(cf_list)-2 of them)
    n_years = len(cf_list) - 2
    for _ in range(n_bootstrap):
        # sample indices for years 1..N
        # idx = np.random.randint(1, 1 + n_years, size=n_years)
        sample = (
            [cf_list[0]]
            + [
                cf_list[np.random.randint(1, 1 + n_years)]  # pick value, keep position
                for _ in range(n_years)
            ]
            + [cf_list[-1]]
        )
        irr_val = npf.irr(sample)
        if irr_val is not None and not np.isnan(irr_val):
            boot_irrs.append(float(irr_val))

    if len(boot_irrs) < 50:
        return None, None

    lower, upper = np.nanpercentile(boot_irrs, ci)
    return float(lower), float(upper)


def run_sensitivity(
    base: Dict[str, Any],
    param: str,
    values: List[float],
    years: int = 5,
    bootstrap: bool = False,
    n_bootstrap: int = 1000,
    ci: Optional[List[float]] = None,
    threads: int = 1,
) -> List[Dict[str, Any]]:
    """
    Run 1D sensitivity on a single parameter.

    Returns a list of dicts, each with:
      - "Param": the parameter name
      - "Value": the tested value
      - "IRR": point estimate IRR
      - "MOIC": point estimate MOIC
      - optionally "IRR_CI_Lower" and "IRR_CI_Upper" if bootstrap=True

    If threads>1 and len(values)>5000, runs models in parallel.
    """
    if ci is None:
        ci = [2.5, 97.5]

    def _run_one(v: float) -> Dict[str, Any]:
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
            # build cashflow list
            eq0 = -model.equity
            cashflows = [run_out[f"Year {i}"]["Equity CF"] for i in range(1, years + 1)]
            exit_eq = summary.get("Equity Value", 0.0)
            cf_list = [eq0] + cashflows + [exit_eq]

            lower, upper = _bootstrap_irr(cf_list, n_bootstrap, ci)
            row["IRR_CI_Lower"] = lower
            row["IRR_CI_Upper"] = upper

        return row

    # decide between serial and threaded
    if threads > 1 and len(values) > 5000:
        with ThreadPoolExecutor(max_workers=threads) as exe:
            results = list(exe.map(_run_one, values))
    else:
        results = [_run_one(v) for v in values]

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
    threads: int = 1,
) -> pd.DataFrame:
    """
    Run 2D sensitivity on two parameters and pivot IRR into a matrix.

    Returns DataFrame of shape :
    (len(values1), len(values2)) with index=values1, columns=values2.
    If heatmap=True, displays interactive heatmap.
    As perf guard: if grid ≥10k combos, asserts runtime <2s.
    Supports optional threading for speed.
    """
    combos = list(itertools.product(values1, values2))
    start = time.time()

    def _one(args: Any) -> Dict[str, Any]:
        v1, v2 = args
        cfg = {**base, param1: v1, param2: v2}
        summary = LBOModel(**cfg).run(years)["Exit Summary"]
        return {param1: v1, param2: v2, "IRR": summary["IRR"], "MOIC": summary["MOIC"]}

    if threads > 1 and len(combos) > 5000:
        with ThreadPoolExecutor(max_workers=threads) as exe:
            data = list(exe.map(_one, combos))
    else:
        data = [_one(c) for c in combos]

    df = pd.DataFrame(data)
    pivot = df.pivot(index=param1, columns=param2, values="IRR")

    if heatmap:
        fig = px.imshow(
            pivot.values,
            x=pivot.columns,
            y=pivot.index[::-1],
            labels={"x": param2, "y": param1, "color": "IRR"},
            **(heatmap_kwargs or {}),
        )
        fig.show()

    if len(combos) >= 10_000:
        duration = time.time() - start
        assert duration < 2.0, f"run_2d_sensitivity too slow: {duration: .3f}s"

    return pivot
