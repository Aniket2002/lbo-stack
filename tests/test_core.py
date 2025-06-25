# tests/test_core.py
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
        bullet_frac=1.0,  # avoid amort insolvency
        amort_frac=0.0,
    )
    res = model.run(years=3)
    assert "Exit Summary" in res
    es = res["Exit Summary"]
    assert es["IRR"] is not None
    assert es["MOIC"] >= 0.0


def test_lbo_covenant_breach():
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
        revolver_limit=0.0,
        revolver_rate=0.0,
        pik_rate=0.0,
        icr_hurdle=10.0,
        bullet_frac=1.0,
        amort_frac=0.0,
    )
    with pytest.raises(CovenantBreachError):
        model.run(years=2)


def test_lbo_insolvency_error():
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
        revolver_rate=0.0,
        pik_rate=0.0,
        bullet_frac=1.0,
        amort_frac=0.0,
    )
    for t in model.debt_tranches:
        t.amort_schedule = [50.0, 50.0]
    with pytest.raises(InsolvencyError):
        model.run(years=2)


def test_revolver_limit_insolvency():
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
        revolver_limit=50.0,
        revolver_rate=0.1,
        pik_rate=0.0,
        bullet_frac=1.0,
        amort_frac=0.0,
    )
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
        bullet_frac=1.0,
        amort_frac=0.0,
    )
    s = model.summary()
    assert "Exit Year:" in s
    assert "IRR:" in s


def test_pik_interest_accrual_and_cash_sweep():
    """PIK tranche should accrue interest and leave levered CF = interest*(1–sweep)."""
    model = LBOModel(
        enterprise_value=100.0,
        debt_pct=0.5,
        revenue=50.0,
        rev_growth=0.0,
        ebitda_margin=0.2,
        capex_pct=0.0,
        wc_pct=0.0,
        tax_rate=0.0,
        exit_multiple=5.0,
        interest_rate=0.1,
        revolver_limit=0.0,
        revolver_rate=0.0,
        pik_rate=0.05,
        cash_sweep_pct=1.0,
        bullet_frac=1.0,
        amort_frac=0.0,
    )
    # Year‐1 PIK interest = 50 * 0.05 = 2.5;
    # EBITDA=10 ⇒ nopat=10–2.5=7.5;
    # sweep on non‐PIK=0 ⇒ Equity CF=7.5
    res = model.run(years=1)
    cf = res["Year 1"]["Equity CF"]
    assert cf == pytest.approx(7.5)
