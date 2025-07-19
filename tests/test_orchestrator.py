from src.modules.orchestrator import load_inputs, simulate_lbo_with_custom_entry_exit


def test_orchestrator_load_inputs():
    params = load_inputs()
    assert "rev_start" in params
    assert 0 < params["entry_multiple"] < 15


def test_simulated_lbo_has_cashflows():
    params = load_inputs()
    _, irr, df = simulate_lbo_with_custom_entry_exit(params)
    assert "Levered CF" in df.columns
    assert df.shape[0] == 5
    assert irr is None or -1 < irr < 1
