from typing import Dict

def calculate_exit(
    final_year_ebitda: float,
    exit_multiple: float,
    debt: float,
    initial_equity: float,
    years: int
) -> Dict[str, float]:
    """
    Calculate terminal value, equity value, and IRR on exit.

    Returns:
        Dict with 'Terminal Value', 'Equity Value', and 'IRR'
    """

    # Input validation
    if initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")
    if years <= 0:
        raise ValueError("years must be > 0")

    # Terminal and equity values
    terminal_value = final_year_ebitda * exit_multiple
    equity_value = terminal_value - debt

    # IRR calculation (always returns a float)
    irr = (equity_value / initial_equity) ** (1 / years) - 1

    return {
        "Terminal Value": terminal_value,
        "Equity Value": equity_value,
        "IRR": irr
    }
