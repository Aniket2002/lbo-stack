from typing import Dict, Union


def calculate_exit(
    final_year_ebitda: float,
    exit_multiple: float,
    debt: float,
    initial_equity: float,
    years: int,
) -> Dict[str, Union[float, None]]:
    """
    Calculate terminal value, equity value, and IRR on exit.

    Returns:
        Dict with 'Terminal Value', 'Equity Value', and 'IRR'
    """
    if years <= 0:
        raise ValueError("Years must be > 0")
    if initial_equity <= 0:
        raise ValueError("Initial equity must be > 0")
    if exit_multiple < 0:
        raise ValueError("Exit multiple must be non-negative")

    terminal_value = final_year_ebitda * exit_multiple
    equity_value = terminal_value - debt

    try:
        irr = (equity_value / initial_equity) ** (1 / years) - 1
    except (ZeroDivisionError, ValueError):
        irr = None

    return {
        "Terminal Value": terminal_value,
        "Equity Value": equity_value,
        "IRR": irr if equity_value > 0 else -1.0,  # cap downside
    }
