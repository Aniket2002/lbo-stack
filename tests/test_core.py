import pytest

from src.modules.lbo_model import CovenantBreachError, InsolvencyError, LBOModel


def test_lbo_basic_run():
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=0.5,
        revenue=50.0,
        rev_growth=0.1,
        ebitda_margin=0.2,
        capex_pct=0.05,
        wc_pct=0.1,
        tax_rate=0.25,
        exit_multiple=8.0,
        interest_rate=0.07,
        revolver_limit=0.0,
        revolver_rate=0.0,
        pik_rate=0.0,
    )
    res = model.run(years=3)
    assert "Exit Summary" in res
    es = res["Exit Summary"]
    assert es["IRR"] is not None
    assert es["MOIC"] >= 0.0


def test_lbo_covenant_breach():
    # Impossible ICR forces breach
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=0.9,
        revenue=10.0,
        rev_growth=0.0,
        ebitda_margin=0.1,
        capex_pct=0.0,
        wc_pct=0.0,
        tax_rate=0.0,
        exit_multiple=5.0,
        interest_rate=0.5,
        icr_hurdle=10.0,
    )
    with pytest.raises(CovenantBreachError):
        model.run(years=2)


def test_lbo_insolvency_error():
    # Heavy amort triggers insolvency without revolver
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=1.0,
        revenue=1.0,
        rev_growth=0.0,
        ebitda_margin=0.0,
        capex_pct=0.0,
        wc_pct=0.0,
        tax_rate=0.0,
        exit_multiple=1.0,
        interest_rate=0.1,
        revolver_limit=0.0,
        pik_rate=0.0,
    )
    # Force amort > cash each year
    for t in model.debt_tranches:
        t.amort_schedule = [50.0, 50.0]
    with pytest.raises(InsolvencyError):
        model.run(years=2)


def test_revolver_limit_insolvency():
    # Shortfall exceeds revolver limit → insolvency
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=1.0,
        revenue=1.0,
        rev_growth=0.0,
        ebitda_margin=0.0,
        capex_pct=0.0,
        wc_pct=0.0,
        tax_rate=0.0,
        exit_multiple=1.0,
        interest_rate=0.1,
        revolver_limit=50.0,  # can only draw up to 50
        revolver_rate=0.1,
        pik_rate=0.0,
    )
    # Force amort > cash + revolver to exceed limit
    for t in model.debt_tranches:
        t.amort_schedule = [100.0, 100.0]
    with pytest.raises(InsolvencyError):
        model.run(years=2)


def test_summary_str():
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=0.5,
        revenue=50.0,
        rev_growth=0.0,
        ebitda_margin=0.2,
        capex_pct=0.05,
        wc_pct=0.1,
        tax_rate=0.2,
        exit_multiple=5.0,
        interest_rate=0.05,
    )
    s = model.summary()
    assert "Exit Year:" in s
    assert "IRR:" in s
