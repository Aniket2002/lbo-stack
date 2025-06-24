from typing import List, Dict, Any
import pandas as pd
from src.modules.lbo_model import LBOModel

def run_sensitivity(
    base_params: Dict[str, Any],
    vary_param: str,
    values: List[float],
    years: int = 5
) -> List[Dict[str, Any]]:
    """
    Run LBOModel for a range of values of a single parameter.

    Args:
        base_params: dictionary of baseline inputs
        vary_param: the parameter to sweep (e.g., "exit_multiple")
        values: list of values to test
        years: projection period

    Returns:
        List of dicts with IRR results per run
    """
    results = []

    for val in values:
        test_params = base_params.copy()
        test_params[vary_param] = val

        model = LBOModel(**test_params)
        output = model.run(years)

        results.append({
            "Param": vary_param,
            "Value": val,
            "IRR": output["Exit Summary"]["IRR"],
            "Equity Value": output["Exit Summary"]["Equity Value"],
            "Terminal Value": output["Exit Summary"]["Terminal Value"]
        })

    return results


def results_to_dataframe(results: list) -> pd.DataFrame:
    """
    Convert list of sensitivity results to a pandas DataFrame.
    """
    return pd.DataFrame(results)


def export_results(results: list, filename: str = "sensitivity_output.csv"):
    """
    Save results to CSV or XLSX based on file extension.
    """
    df = results_to_dataframe(results)
    if filename.endswith(".xlsx"):
        df.to_excel(filename, index=False)
    else:
        df.to_csv(filename, index=False)

def run_2d_sensitivity(
    base_params: Dict[str, Any],
    row_param: str,
    row_values: List[float],
    col_param: str,
    col_values: List[float],
    years: int = 5,
    metric: str = "IRR"
) -> pd.DataFrame:
    """
    Run LBOModel over a grid of (row_param × col_param) and return a 2D DataFrame.

    Args:
        base_params: baseline parameters
        row_param: varied along rows (e.g. 'rev_growth')
        row_values: list of row values
        col_param: varied along columns (e.g. 'exit_multiple')
        col_values: list of column values
        years: projection period
        metric: output metric ("IRR", "Equity Value", etc.)

    Returns:
        pd.DataFrame with row_param as index, col_param as columns
    """
    data = []

    for row_val in row_values:
        row = []
        for col_val in col_values:
            params = base_params.copy()
            params[row_param] = row_val
            params[col_param] = col_val

            model = LBOModel(**params)
            result = model.run(years)
            row.append(result["Exit Summary"][metric])
        data.append(row)

    return pd.DataFrame(data, index=row_values, columns=col_values)
