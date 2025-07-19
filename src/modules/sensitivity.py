# src/modules/sensitivity.py

import inspect
import itertools
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy_financial as npf
import pandas as pd
import plotly.express as px

from src.modules.lbo_model import InsolvencyError, LBOModel

# configure module‐level logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _bootstrap_irr(
    cf_list: List[float], n_bootstrap: int, ci: List[float]
) -> Tuple[float, float]:
    irrs = []
    for _ in range(n_bootstrap):
        sample = list(np.random.choice(cf_list, size=len(cf_list), replace=True))
        irr = npf.irr(sample)
        if irr is not None and not np.isnan(irr):
            irrs.append(irr)
    if not irrs:
        return (float("nan"), float("nan"))
    lower = float(np.percentile(irrs, ci[0]))
    upper = float(np.percentile(irrs, ci[1]))
    return lower, upper


def _filter_cfg_for_lbo(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop any keys not present in LBOModel.__init__ signature.
    """
    sig = inspect.signature(LBOModel.__init__)
    valid = set(sig.parameters) - {"self", "args", "kwargs"}
    return {k: v for k, v in cfg.items() if k in valid}


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
    if ci is None:
        ci = [2.5, 97.5]

    def _run_one(v: float) -> Dict[str, Any]:
        cfg = base.copy()
        cfg[param] = v
        # filter out stray keys like 'revenue0'
        lbo_kwargs = _filter_cfg_for_lbo(cfg)

        try:
            model = LBOModel(**lbo_kwargs)
            # disable scheduled amort to avoid insolvency
            for t in model.debt_tranches:
                if t.name in ("Senior", "Mezzanine"):
                    t.amort = False

            run_out = model.run(years)
            summary = run_out["Exit Summary"]
            irr = summary["IRR"]
            moic = summary["MOIC"]
        except InsolvencyError as ie:
            log.warning(f"Insolvency at {param}={v}: {ie}")
            return {"Param": param, "Value": v, "IRR": None, "MOIC": None}
        except Exception as e:
            log.error(f"Error at {param}={v}: {e}")
            return {"Param": param, "Value": v, "IRR": None, "MOIC": None}

        row = {"Param": param, "Value": v, "IRR": irr, "MOIC": moic}

        if bootstrap:
            eq0 = -model.equity
            cashflows = [run_out[f"Year {i}"]["Equity CF"] for i in range(1, years + 1)]
            exit_eq = summary.get("Equity Value", 0.0)
            cf_list = [eq0] + cashflows + [exit_eq]
            lower, upper = _bootstrap_irr(cf_list, n_bootstrap, ci)
            row["IRR_CI_Lower"] = lower
            row["IRR_CI_Upper"] = upper

        return row

    if threads > 1 and len(values) > 5000:
        with ThreadPoolExecutor(max_workers=threads) as exe:
            return list(exe.map(_run_one, values))
    else:
        return [_run_one(v) for v in values]


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
    combos = list(itertools.product(values1, values2))
    start = time.time()

    def _one(args: Any) -> Dict[str, Any]:
        v1, v2 = args
        cfg = base.copy()
        cfg[param1] = v1
        cfg[param2] = v2
        # filter before instantiation
        lbo_kwargs = _filter_cfg_for_lbo(cfg)

        model = LBOModel(**lbo_kwargs)
        for t in model.debt_tranches:
            if t.name in ("Senior", "Mezzanine"):
                t.amort = False
        summary = model.run(years)["Exit Summary"]
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
        assert duration < 2.0, f"run_2d_sensitivity too slow: {duration:.3f}s"

    return pivot
