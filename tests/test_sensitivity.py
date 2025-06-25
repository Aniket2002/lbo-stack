import pandas as pd

from src.modules.sensitivity import (
    export_results,
    results_to_dataframe,
    run_2d_sensitivity,
    run_sensitivity,
)


def test_run_sensitivity_irrs():
    base = {
        "enterprise_value": 100.0,
        "debt_pct": 0.5,
        "revenue": 50.0,
        "rev_growth": 0.0,
        "ebitda_margin": 0.2,
        "capex_pct": 0.05,
        "wc_pct": 0.1,
        "tax_rate": 0.25,
        "exit_multiple": 8.0,
        "interest_rate": 0.07,
    }
    results = run_sensitivity(base, "exit_multiple", [6.0, 8.0], years=2)
    assert len(results) == 2
    df = results_to_dataframe(results)
    assert list(df["Value"]) == [6.0, 8.0]


def test_export_results(tmp_path):
    data = [{"Param": "x", "Value": 1, "IRR": 0.1}]
    csv_file = tmp_path / "out.csv"
    export_results(data, filename=str(csv_file))
    assert csv_file.exists()
    df = pd.read_csv(str(csv_file))
    assert df.loc[0, "Param"] == "x"


def test_run_2d_sensitivity_shape():
    base = {
        "enterprise_value": 100.0,
        "debt_pct": 0.5,
        "revenue": 50.0,
        "rev_growth": 0.0,
        "ebitda_margin": 0.2,
        "capex_pct": 0.05,
        "wc_pct": 0.1,
        "tax_rate": 0.25,
        "exit_multiple": 8.0,
        "interest_rate": 0.07,
    }
    df2d = run_2d_sensitivity(
        base, "rev_growth", [0.0, 0.1], "exit_multiple", [6.0, 8.0], years=2
    )
    assert df2d.shape == (2, 2)
