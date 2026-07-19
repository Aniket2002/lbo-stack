import math
import unittest

from src.modules.fund_waterfall import compute_waterfall_by_year
from src.modules.orchestrator_advanced import (
    DealAssumptions,
    build_canonical_sources_and_uses,
    build_exit_equity_bridge,
    monte_carlo_analysis,
    run_enhanced_base_case,
)


class FinancialInvariantTests(unittest.TestCase):
    def test_sources_equal_uses(self):
        assumptions = DealAssumptions()
        schedule = build_canonical_sources_and_uses(assumptions)

        self.assertTrue(schedule["sources_equals_uses"])
        self.assertAlmostEqual(
            schedule["sources"]["Total Sources"],
            schedule["uses"]["Total Uses"],
            places=6,
        )

    def test_debt_and_cash_roll_forward_reconcile(self):
        assumptions = DealAssumptions()
        results, metrics = run_enhanced_base_case(assumptions)

        self.assertLess(metrics["Debt_Roll_Forward_Max_Delta"], 1e-6)
        self.assertLess(metrics["Cash_Roll_Forward_Max_Delta"], 1e-6)

        for year in range(1, assumptions.years + 1):
            row = results[f"Year {year}"]
            opening_debt = row["Opening Debt"]
            opening_cash = row["Opening Cash"]
            closing_debt = row["Closing Debt"]
            closing_cash = row["Closing Cash"]
            debt_draws = row["Debt Draws"]
            pik_interest = row["PIK Interest"]
            debt_repayments = row["Debt Repayments"]
            amortisation = row["Scheduled Amortization"]
            optional_sweep = row["Optional Cash Sweep"]
            operating_cf = row["Cash Available for Debt Service"]

            self.assertAlmostEqual(
                opening_debt + debt_draws + pik_interest - debt_repayments,
                closing_debt,
                places=6,
            )
            self.assertAlmostEqual(
                opening_cash + operating_cf + debt_draws - amortisation - optional_sweep,
                closing_cash,
                places=6,
            )

    def test_exit_bridge_reconciles_to_metrics(self):
        assumptions = DealAssumptions()
        results, metrics = run_enhanced_base_case(assumptions)
        bridge = build_exit_equity_bridge(results, metrics, assumptions)

        self.assertAlmostEqual(
            bridge["exit_equity_value"],
            metrics["Equity Value"],
            places=6,
        )
        self.assertAlmostEqual(
            bridge["exit_ev"] - bridge["final_net_debt"] - bridge["sale_costs"],
            bridge["exit_equity_value"],
            places=6,
        )

    def test_monte_carlo_uses_all_scenarios(self):
        assumptions = DealAssumptions()
        mc_results = monte_carlo_analysis(assumptions, n=25, seed=7)

        self.assertEqual(mc_results["Count"], 25)
        self.assertEqual(len(mc_results["Scenarios"]), 25)
        self.assertEqual(len(mc_results["IRRs"]), 25)
        self.assertAlmostEqual(
            mc_results["Success_Rate"],
            mc_results["Successful_Count"] / mc_results["Count"],
            places=10,
        )
        self.assertEqual(mc_results["Seed"], 7)

    def test_multi_tier_waterfall_reconciles_each_year(self):
        waterfall = compute_waterfall_by_year(
            committed_capital=100.0,
            capital_calls=[20.0, 0.0, 0.0],
            distributions=[0.0, 10.0, 120.0],
            tiers=[
                {"hurdle": 0.08, "carry": 0.20},
                {"hurdle": 0.15, "carry": 0.30},
            ],
            gp_commitment=0.02,
            mgmt_fee_pct=0.0,
            mgmt_fee_basis="committed",
            reset_hurdle=False,
            cashless=False,
            clawback_interest="simple",
        )

        self.assertEqual(len(waterfall), 3)
        self.assertEqual(len(waterfall[-1]["Tier Detail"]), 2)
        for row in waterfall:
            self.assertAlmostEqual(
                row["Gross Distribution Reconciliation"],
                row["Gross Dist"],
                places=6,
            )
            self.assertAlmostEqual(
                row["LP + GP Reconciliation"],
                row["LP Distributed"] + row["GP Distributed"],
                places=6,
            )

    def test_cashless_carry_and_clawback_generate_final_adjustment(self):
        waterfall = compute_waterfall_by_year(
            committed_capital=100.0,
            capital_calls=[50.0, 0.0, 0.0],
            distributions=[0.0, 0.0, 200.0],
            tiers=[{"hurdle": 0.08, "carry": 0.20}],
            gp_commitment=0.02,
            mgmt_fee_pct=0.0,
            mgmt_fee_basis="committed",
            reset_hurdle=False,
            cashless=True,
            clawback_interest="simple",
        )

        self.assertIn("GP Final Pay", waterfall[-1])
        self.assertGreater(waterfall[-1].get("GP Final Pay", 0.0), 0.0)
        self.assertIn("Clawback", waterfall[-1])
        self.assertGreaterEqual(waterfall[-1].get("GP Net After Clawback", 0.0), 0.0)
        self.assertTrue(math.isfinite(waterfall[-1]["LP IRR"]))


if __name__ == "__main__":
    unittest.main()
