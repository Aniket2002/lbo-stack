from src.modules.fund_waterfall import compute_waterfall_by_year


def test_waterfall_outputs_valid_result():
    committed = 100_000_000.0
    calls = [30_000_000.0, 20_000_000.0, 10_000_000.0]
    distributions = [0.0, 25_000_000.0, 80_000_000.0]

    result = compute_waterfall_by_year(
        committed_capital=committed, capital_calls=calls, distributions=distributions
    )
    assert isinstance(result, list)
    assert isinstance(result[-1], dict)
    assert any(
        k in result[-1] for k in ["GP Called", "GP Carry", "GP IRR", "Capital Called"]
    )
