import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.sensitivity import run_sensitivity

def test_run_sensitivity_exit_multiple():
    base = {
        "enterprise_value": 100e6,
        "debt_pct": 0.6,
        "revenue": 50e6,
        "rev_growth": 0.10,
        "ebitda_margin": 0.20,
        "capex_pct": 0.05,
        "exit_multiple": 8.0,
        "interest_rate": 0.07
    }

    results = run_sensitivity(base, "exit_multiple", [6.0, 7.0, 8.0], years=5)

    assert len(results) == 3
    for r in results:
        assert r["Param"] == "exit_multiple"
        assert isinstance(r["IRR"], float)

