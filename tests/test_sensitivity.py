from src.modules.sensitivity import run_2d_sensitivity, run_sensitivity


def test_1d_sensitivity_run_valid():
    base = {
        "enterprise_value": 1000,
        "debt_pct": 0.6,
        "senior_frac": 0.4,
        "mezz_frac": 0.2,
        "revenue": 200,
        "rev_growth": 0.05,
        "ebitda_margin": 0.25,
        "capex_pct": 0.1,
        "wc_pct": 0.1,
        "tax_rate": 0.3,
        "exit_multiple": 8.0,
        "senior_rate": 0.06,
        "mezz_rate": 0.09,
    }
    result = run_sensitivity(base, param="rev_growth", values=[0.01, 0.05])
    assert len(result) == 2
    assert all("IRR" in r for r in result)


def test_2d_sensitivity_returns_matrix():
    base = {
        "enterprise_value": 1000,
        "debt_pct": 0.6,
        "senior_frac": 0.4,
        "mezz_frac": 0.2,
        "revenue": 200,
        "rev_growth": 0.05,
        "ebitda_margin": 0.25,
        "capex_pct": 0.1,
        "wc_pct": 0.1,
        "tax_rate": 0.3,
        "exit_multiple": 8.0,
        "senior_rate": 0.06,
        "mezz_rate": 0.09,
    }
    df = run_2d_sensitivity(base, "rev_growth", [0.01, 0.05], "exit_multiple", [7, 8])
    assert df.shape == (2, 2)
