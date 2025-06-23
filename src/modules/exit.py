def calculate_exit(
    final_year_ebitda: float,
    exit_multiple: float,
    debt: float,
    initial_equity: float,
    years: int
) -> dict:
    """
    Calculate terminal value, equity value, and IRR on exit.

    Returns:
        Dict with 'Terminal Value', 'Equity Value', 'IRR'
    """
    terminal_value = final_year_ebitda * exit_multiple
    equity_value = terminal_value - debt
    irr = (equity_value / initial_equity) ** (1 / years) - 1

    return {
        "Terminal Value": terminal_value,
        "Equity Value": equity_value,
        "IRR": irr
    }
