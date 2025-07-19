import pytest

from src.modules.lbo_model import CovenantBreachError, LBOModel


def test_lbo_model_outputs_valid_keys():
    model = LBOModel(
        enterprise_value=1000.0,
        debt_pct=0.4,  # reduced total leverage
        senior_frac=0.6,
        mezz_frac=0.4,
        revenue=500.0,  # boost initial revenue
        rev_growth=0.05,
        ebitda_margin=0.4,  # more EBITDA
        capex_pct=0.02,  # reduced capital drain
        wc_pct=0.01,  # smaller WC draw
        tax_rate=0.25,
        exit_multiple=8.0,
        senior_rate=0.04,
        mezz_rate=0.07,
    )
    output = model.run()
    assert "Exit Summary" in output
    assert "IRR" in output["Exit Summary"]


def test_lbo_model_icr_breach():
    model = LBOModel(
        enterprise_value=1000,
        debt_pct=0.7,
        senior_frac=0.7,
        mezz_frac=0.3,
        revenue=100,
        rev_growth=0.0,
        ebitda_margin=0.1,
        capex_pct=0.1,
        wc_pct=0.1,
        tax_rate=0.3,
        exit_multiple=8.0,
        senior_rate=0.3,
        mezz_rate=0.3,
        icr_hurdle=2.5,
    )
    with pytest.raises(CovenantBreachError):
        model.run()
