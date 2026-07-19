import unittest

from src.modules.lbo_model import LBOModel
from src.modules.fund_waterfall import compute_waterfall_by_year


class FundWaterfallTests(unittest.TestCase):
    def test_lp_and_gp_distributions_reconcile_to_gross_distributions(self):
        waterfall = compute_waterfall_by_year(
            committed_capital=100.0,
            capital_calls=[20.0, 20.0, 20.0],
            distributions=[0.0, 25.0, 50.0],
            tiers=[{"type": "irr", "rate": 0.08, "carry": 0.20}],
            gp_commitment=0.02,
            mgmt_fee_pct=0.0,
            mgmt_fee_basis="committed",
            reset_hurdle=False,
            cashless=False,
            clawback_interest="simple",
        )

        for year in waterfall:
            self.assertAlmostEqual(
                year["LP Distributions + GP Distributions"],
                year["Gross Dist"],
                places=10,
            )

    def test_yearly_entries_include_reconciliation_fields(self):
        waterfall = compute_waterfall_by_year(
            committed_capital=100.0,
            capital_calls=[10.0],
            distributions=[15.0],
            tiers=[{"type": "irr", "rate": 0.08, "carry": 0.20}],
            gp_commitment=0.02,
            mgmt_fee_pct=0.0,
            mgmt_fee_basis="committed",
            reset_hurdle=False,
            cashless=False,
            clawback_interest="simple",
        )

        self.assertIn("LP Distributed", waterfall[0])
        self.assertIn("GP Distributed", waterfall[0])
        self.assertIn("LP Distributions + GP Distributions", waterfall[0])

    def test_exit_proceeds_are_folded_into_the_final_cashflow_period(self):
        model = LBOModel(
            enterprise_value=100.0,
            debt_pct=0.5,
            senior_frac=0.5,
            mezz_frac=0.0,
            revenue=100.0,
            rev_growth=0.0,
            ebitda_margin=0.2,
            capex_pct=0.0,
            wc_pct=0.0,
            tax_rate=0.0,
            exit_multiple=5.0,
            senior_rate=0.0,
            mezz_rate=0.0,
            da_pct=0.0,
            cash_sweep_pct=0.0,
        )

        results = model.run(years=5)
        vector = results["Exit Summary"]["Equity Cash Flow Vector"]

        self.assertEqual(len(vector), 6)
        self.assertGreater(results["Exit Summary"]["Equity Value"], 0.0)
        self.assertGreater(vector[-1], results["Year 5"]["Equity CF"])


if __name__ == "__main__":
    unittest.main()
