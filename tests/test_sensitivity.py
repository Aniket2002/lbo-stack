# tests/test_sensitivity.py
# import pandas as pd
# import pytest

from src.modules.sensitivity import (
    results_to_dataframe,
    run_2d_sensitivity,
    run_sensitivity,
)


def base_config():
    return dict(
        enterprise_value=100.0,
        debt_pct=0.5,
        revenue=50.0,
        rev_growth=0.0,
        ebitda_margin=0.2,
        capex_pct=0.05,
        wc_pct=0.1,
        tax_rate=0.25,
        exit_multiple=8.0,
        interest_rate=0.07,
        bullet_frac=1.0,
        amort_frac=0.0,
    )


def test_run_sensitivity_basic_and_dataframe():
    base = base_config()
    results = run_sensitivity(base, "exit_multiple", [6.0, 7.0], years=3)
    assert len(results) == 2
    df = results_to_dataframe(results)
    assert list(df["Value"]) == [6.0, 7.0]


def test_bootstrap_ci_edge_cases(monkeypatch):
    base = base_config()
    # force irr→None on all draws
    import numpy_financial as npf

    monkeypatch.setattr(npf, "irr", lambda cf: None)
    out = run_sensitivity(
        base, "exit_multiple", [4.0], years=1, bootstrap=True, n_bootstrap=10
    )
    # with <50 valid draws, CI should be None
    row = out[0]
    assert row["IRR_CI_Lower"] is None
    assert row["IRR_CI_Upper"] is None


def test_run_2d_sensitivity_shape_and_values():
    base = base_config()
    df2 = run_2d_sensitivity(
        base, "rev_growth", [0.0, 0.1], "exit_multiple", [6.0, 7.0], years=2
    )
    assert df2.shape == (2, 2)
    # ensure index and columns align
    assert list(df2.index) == [0.0, 0.1]
    assert list(df2.columns) == [6.0, 7.0]
