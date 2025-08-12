#!/usr/bin/env python3
"""
Unit tests for LBO model to prevent future weirdness
Tests recommended by PE VP feedback
"""

import os
import sys

import pytest

sys.path.append("src/modules")

from lbo_model import LBOModel
from orchestrator_advanced import (
    DealAssumptions,
    build_enhanced_lbo_config,
    run_enhanced_base_case,
)


def test_margin_moves_irr():
    """Test that higher EBITDA margin produces higher IRR"""
    base = DealAssumptions()

    # Low margin case
    low_assumptions = DealAssumptions(
        **{**base.__dict__, "ebitda_margin_start": base.ebitda_margin_start - 0.03}
    )

    # High margin case
    high_assumptions = DealAssumptions(
        **{**base.__dict__, "ebitda_margin_start": base.ebitda_margin_start + 0.03}
    )

    try:
        _, low_metrics = run_enhanced_base_case(low_assumptions)
        _, high_metrics = run_enhanced_base_case(high_assumptions)

        low_irr = low_metrics.get("IRR", float("nan"))
        high_irr = high_metrics.get("IRR", float("nan"))

        # Higher margin should produce higher IRR
        assert (
            high_irr > low_irr
        ), f"Higher margin IRR ({high_irr:.1%}) should exceed lower margin IRR ({low_irr:.1%})"

    except Exception as e:
        pytest.fail(f"Margin sensitivity test failed: {e}")


def test_cashflow_signs():
    """Test that equity cashflows have correct signs (negative upfront, positive returns)"""
    base = DealAssumptions()

    try:
        results, metrics = run_enhanced_base_case(base)

        # Check if we have equity cashflow data
        equity_cfs = []
        for year in range(1, base.years + 1):
            year_key = f"Year {year}"
            if year_key in results:
                equity_cf = results[year_key].get("equity_cf", 0)
                equity_cfs.append(equity_cf)

        # Should have some cashflows
        assert len(equity_cfs) > 0, "No equity cashflows found"

        # At least one positive cashflow (returns)
        assert any(
            cf > 0 for cf in equity_cfs
        ), f"No positive equity cashflows found: {equity_cfs}"

        # Exit should be positive if model works
        exit_value = metrics.get("exit_equity_value", 0)
        if exit_value != "N/A":
            assert exit_value > 0, f"Exit equity value should be positive: {exit_value}"

    except Exception as e:
        pytest.fail(f"Cashflow signs test failed: {e}")


def test_exit_multiple_sensitivity():
    """Test that higher exit multiple produces higher IRR"""
    base = DealAssumptions()

    # Low multiple case
    low_assumptions = DealAssumptions(
        **{**base.__dict__, "exit_ev_ebitda": base.exit_ev_ebitda - 1.0}
    )

    # High multiple case
    high_assumptions = DealAssumptions(
        **{**base.__dict__, "exit_ev_ebitda": base.exit_ev_ebitda + 1.0}
    )

    try:
        _, low_metrics = run_enhanced_base_case(low_assumptions)
        _, high_metrics = run_enhanced_base_case(high_assumptions)

        low_irr = low_metrics.get("IRR", float("nan"))
        high_irr = high_metrics.get("IRR", float("nan"))

        # Higher exit multiple should produce higher IRR
        assert (
            high_irr > low_irr
        ), f"Higher multiple IRR ({high_irr:.1%}) should exceed lower multiple IRR ({low_irr:.1%})"

    except Exception as e:
        pytest.fail(f"Exit multiple sensitivity test failed: {e}")


def test_moic_irr_consistency():
    """Test that MOIC and IRR are directionally consistent"""
    base = DealAssumptions()

    try:
        _, metrics = run_enhanced_base_case(base)

        irr = metrics.get("IRR", float("nan"))
        moic = metrics.get("MOIC", float("nan"))

        # Basic sanity checks
        if not (irr != irr):  # Check if IRR is not NaN
            if moic > 1.0:
                # If MOIC > 1, IRR should be positive
                assert (
                    irr > 0
                ), f"MOIC {moic:.2f}x > 1 but IRR {irr:.1%} is not positive"
            elif moic < 1.0:
                # If MOIC < 1, IRR should be negative
                assert (
                    irr < 0
                ), f"MOIC {moic:.2f}x < 1 but IRR {irr:.1%} is not negative"

    except Exception as e:
        pytest.fail(f"MOIC-IRR consistency test failed: {e}")


def test_covenant_calculation():
    """Test that covenant calculations are working properly"""
    base = DealAssumptions()

    try:
        results, metrics = run_enhanced_base_case(base)

        # Check covenant metrics exist
        assert "Min_ICR" in metrics, "Missing Min_ICR metric"
        assert "Max_LTV" in metrics, "Missing Max_LTV metric"

        min_icr = metrics["Min_ICR"]
        max_ltv = metrics["Max_LTV"]

        # Sanity checks
        assert min_icr > 0, f"ICR should be positive: {min_icr}"
        assert max_ltv > 0, f"LTV should be positive: {max_ltv}"

        # Check headroom calculations
        if "ICR_Headroom" in metrics:
            icr_headroom = metrics["ICR_Headroom"]
            expected_headroom = min_icr - base.icr_hurdle
            assert (
                abs(icr_headroom - expected_headroom) < 1e-6
            ), f"ICR headroom mismatch: got {icr_headroom}, expected {expected_headroom}"

    except Exception as e:
        pytest.fail(f"Covenant calculation test failed: {e}")


if __name__ == "__main__":
    # Run tests
    print("Running LBO model unit tests...")

    try:
        test_margin_moves_irr()
        print("✅ Margin sensitivity test passed")
    except Exception as e:
        print(f"❌ Margin sensitivity test failed: {e}")

    try:
        test_cashflow_signs()
        print("✅ Cashflow signs test passed")
    except Exception as e:
        print(f"❌ Cashflow signs test failed: {e}")

    try:
        test_exit_multiple_sensitivity()
        print("✅ Exit multiple sensitivity test passed")
    except Exception as e:
        print(f"❌ Exit multiple sensitivity test failed: {e}")

    try:
        test_moic_irr_consistency()
        print("✅ MOIC-IRR consistency test passed")
    except Exception as e:
        print(f"❌ MOIC-IRR consistency test failed: {e}")

    try:
        test_covenant_calculation()
        print("✅ Covenant calculation test passed")
    except Exception as e:
        print(f"❌ Covenant calculation test failed: {e}")

    print("Unit tests completed!")
