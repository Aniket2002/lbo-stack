import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from modules.exit import calculate_exit

def test_calculate_exit():
    result = calculate_exit(
        final_year_ebitda=20_000_000,
        exit_multiple=8.0,
        debt=60_000_000,
        initial_equity=40_000_000,
        years=5
    )

    assert round(result["Terminal Value"]) == 160_000_000
    assert round(result["Equity Value"]) == 100_000_000
    assert round(result["IRR"], 4) == round((100_000_000 / 40_000_000) ** (1/5) - 1, 4)
