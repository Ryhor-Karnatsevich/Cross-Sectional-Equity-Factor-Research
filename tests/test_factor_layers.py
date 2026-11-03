import os
import importlib.util
import sys
import unittest
from unittest.mock import mock_open, patch

import numpy as np
import pandas as pd


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
FACTOR_LAYER_PATH = os.path.join(PROJECT_ROOT, "src", "Factors_Layer")
SELECTION_LAYER_PATH = os.path.join(
    PROJECT_ROOT,
    "src",
    "Factor_Selection_Layer",
)

for path in (FACTOR_LAYER_PATH, SELECTION_LAYER_PATH):
    if path not in sys.path:
        sys.path.insert(0, path)

from forward_returns import compute_forward_returns
from quantile_analysis import (
    aggregate_quantile_relationships,
    compute_daily_relationship_metrics,
    prepare_factor_quantiles,
)
import hypothesis_analysis
pipeline_spec = importlib.util.spec_from_file_location(
    "selection_pipeline_tests", os.path.join(SELECTION_LAYER_PATH, "pipeline.py")
)
selection_pipeline = importlib.util.module_from_spec(pipeline_spec)
pipeline_spec.loader.exec_module(selection_pipeline)
from hypothesis_analysis import daily_effects
from pattern_classification import apply_multiple_testing, classify_hypotheses, classify_pattern, evidence_status
from selection_config import EFFECT_NAMES
from selection_report import selection_conclusion


class FactorLayerTest(unittest.TestCase):
    def test_forward_return_requires_quality_at_both_endpoints(self):
        dates = pd.date_range("2020-01-01", periods=3, freq="D")
        prices = pd.DataFrame(
            {"A": [100.0, 110.0, 121.0], "B": [50.0, 55.0, 60.0]},
            index=dates,
        )
        quality = pd.DataFrame(True, index=dates, columns=prices.columns)
        quality.loc[dates[1], "B"] = False

        result = compute_forward_returns(prices, quality, horizon=1)

        self.assertAlmostEqual(result.loc[dates[0], "A"], 0.10)
        self.assertAlmostEqual(result.loc[dates[1], "A"], 0.10)
        self.assertTrue(pd.isna(result.loc[dates[0], "B"]))
        self.assertTrue(pd.isna(result.loc[dates[1], "B"]))
        self.assertTrue(result.loc[dates[2]].isna().all())


class FactorSelectionLayerTest(unittest.TestCase):
    def saved_metric_example(self):
        card = {"hypothesis_key": "demo|variant|h1", "factor_key": "demo|variant",
                "horizon_days": 1, "valid_ic_ratio": 1.0,
                "quantile_curve_rho": 0.95, "quantile_step_ratio": 0.8}
        rows = []
        for effect in EFFECT_NAMES:
            for metric, value in (("mean", 0.01), ("hac_tstat", 3.0),
                                  ("monthly_direction_rate", 0.8),
                                  ("annual_direction_rate", 0.8)):
                card[f"{effect}_{metric}"] = value
            rows.append({"hypothesis_key": card["hypothesis_key"], "effect": effect,
                         "mean": 0.01, "median": 0.01, "hac_tstat": 3.0,
                         "raw_p_value": 0.0027, "monthly_direction_rate": 0.8,
                         "annual_direction_rate": 0.8, "valid_date_ratio": 1.0})
        return pd.DataFrame([card]), pd.DataFrame(rows)

    def test_saved_cards_can_be_reclassified_without_duplicate_columns(self):
        cards, effects = self.saved_metric_example()
        first_cards, first_effects = classify_hypotheses(cards, effects, 1)
        repeated_cards, repeated_effects = classify_hypotheses(first_cards, first_effects, 1)
        pd.testing.assert_frame_equal(first_cards, repeated_cards)
        pd.testing.assert_frame_equal(first_effects, repeated_effects)
        np.testing.assert_allclose(repeated_effects["raw_p_value"], effects["raw_p_value"])

    def test_correction_only_never_calls_quantile_or_statistical_analysis(self):
        cards, effects = self.saved_metric_example()
        cards, effects = classify_hypotheses(cards, effects, 1)
        saved = (cards, effects, pd.DataFrame(), pd.DataFrame(), 1)
        old_metadata = '{"created_at_utc":"2026-11-02T23:00:00+00:00"}'
        with patch.object(selection_pipeline, "prepare_selection_directories"), \
             patch.object(selection_pipeline, "prepare_quantile_data", side_effect=AssertionError("Quantiles rerun")), \
             patch.object(selection_pipeline, "build_hypothesis_metrics", side_effect=AssertionError("Statistics rerun")), \
             patch.object(selection_pipeline, "load_saved_hypothesis_metrics", return_value=saved), \
             patch.object(selection_pipeline, "run_classifier_validation", return_value=pd.DataFrame({"passed":[True]})), \
             patch.object(selection_pipeline, "create_selection_figures", return_value=[]), \
             patch.object(selection_pipeline, "build_selection_report", return_value="report"), \
             patch.object(selection_pipeline, "save_csv"), \
             patch.object(selection_pipeline, "save_parquet") as save_parquet, \
             patch.object(selection_pipeline, "save_text"), \
             patch.object(selection_pipeline, "save_json") as save_json, \
             patch("builtins.open", mock_open(read_data=old_metadata)):
            selection_pipeline.run_pipeline(correction_only=True)
        save_parquet.assert_not_called()
        metadata = save_json.call_args.args[0]
        self.assertTrue(metadata["statistical_metrics_reused"])
        self.assertEqual(metadata["hypothesis_metrics_created_at_utc"], "2026-11-02T23:00:00+00:00")

    def test_correction_only_rejects_outdated_quantile_cache(self):
        with patch.object(hypothesis_analysis, "quantile_cache_is_valid", return_value=False):
            with self.assertRaisesRegex(ValueError, "normal Selection pipeline"):
                hypothesis_analysis.load_saved_hypothesis_metrics()

    def test_correction_only_rejects_statistics_older_than_quantile_data(self):
        old_selection = '{"created_at_utc":"2026-11-03T12:00:00+00:00","hypothesis_metrics_created_at_utc":"2026-11-01T12:00:00+00:00"}'
        new_quantiles = '{"created_at_utc":"2026-11-02T12:00:00+00:00"}'
        with patch.object(hypothesis_analysis, "quantile_cache_is_valid", return_value=True), \
             patch("builtins.open", side_effect=[mock_open(read_data=old_selection)(), mock_open(read_data=new_quantiles)()]):
            with self.assertRaisesRegex(ValueError, "predate"):
                hypothesis_analysis.load_saved_hypothesis_metrics()

    def test_bh_is_separate_by_effect_and_retains_pooled_comparison(self):
        rows = [
            {"hypothesis_key": f"h{i}", "effect": effect,
             "raw_p_value": (0.01, 0.04)[i] if effect == "spearman_ic" else 1.0}
            for effect in EFFECT_NAMES for i in range(2)
        ]
        result = apply_multiple_testing(pd.DataFrame(rows), factor_count=1)
        ic = result.loc[result["effect"].eq("spearman_ic")]
        np.testing.assert_allclose(ic["bh_q_value_within_effect"], [0.02, 0.04])
        self.assertTrue(ic["reject_within_effect_fdr"].all())
        self.assertFalse(ic["reject_global_fdr"].any())
        pd.testing.assert_series_equal(
            result["reject_active_scope_fdr"], result["reject_within_effect_fdr"],
            check_names=False,
        )
        np.testing.assert_allclose(result["raw_p_value"], [r["raw_p_value"] for r in rows])

    def test_bh_keeps_missing_values_and_nonconsecutive_indices(self):
        frame = pd.DataFrame(
            {"hypothesis_key": ["a", "b", "c"],
             "effect": ["spearman_ic", "spearman_ic", "q10_minus_q1"],
             "raw_p_value": [0.04, np.nan, 1.0]}, index=[8, 2, 15],
        )
        result = apply_multiple_testing(frame, factor_count=1)
        self.assertEqual(result.index.tolist(), [8, 2, 15])
        self.assertAlmostEqual(result.loc[8, "bh_q_value_within_effect"], 0.04)
        self.assertTrue(pd.isna(result.loc[2, "bh_q_value_within_effect"]))
        self.assertFalse(result.loc[2, "reject_within_effect_fdr"])
        self.assertEqual(result.loc[8, "effect_family_test_count"], 2)
        self.assertEqual(result.loc[8, "effect_family_valid_test_count"], 1)

    def test_full_scope_has_five_groups_of_448(self):
        rows = [
            {"hypothesis_key": f"h{i}", "effect": effect, "raw_p_value": 0.5}
            for effect in EFFECT_NAMES for i in range(448)
        ]
        result = apply_multiple_testing(pd.DataFrame(rows), factor_count=56)
        self.assertTrue(result["full_research_scope"].all())
        self.assertTrue(result["effect_family_test_count"].eq(448).all())

    def test_candidate_uses_per_effect_q_and_still_requires_time_stability(self):
        row = {"valid_ic_ratio": 1.0, "pattern": "upper_tail",
               "primary_effect_hac_tstat": 2.5,
               "primary_effect_monthly_direction_rate": 0.8,
               "primary_effect_annual_direction_rate": 0.8,
               "full_research_scope": True,
               "primary_effect_bh_q_active_scope": 0.04,
               "primary_effect_bh_q_global": 0.20}
        self.assertEqual(evidence_status(row), "candidate_after_effect_fdr")
        row["primary_effect_monthly_direction_rate"] = 0.2
        self.assertEqual(evidence_status(row), "time_unstable_pattern")

    def test_selection_conclusion_separates_ic_from_economic_effects(self):
        cards = pd.DataFrame(
            [{"evidence_status": "rejected_by_multiple_testing"}]
        )
        effects = pd.DataFrame(
            [
                {
                    "effect": "spearman_ic",
                    "reject_active_scope_fdr": True,
                },
                {
                    "effect": "q10_minus_q1",
                    "reject_active_scope_fdr": False,
                },
            ]
        )

        conclusion = "\n".join(
            selection_conclusion(cards, effects, full_scope=True)
        )

        self.assertIn("Rank-IC discoveries after per-effect FDR: `1`", conclusion)
        self.assertIn(
            "Economic-effect discoveries after per-effect FDR: `0`",
            conclusion,
        )

    def test_lagged_factor_is_ranked_before_future_returns_are_used(self):
        dates = pd.date_range("2020-01-01", periods=2, freq="D")
        tickers = [f"T{number:02d}" for number in range(30)]
        factor = pd.DataFrame(
            [np.arange(30), np.arange(30) + 100],
            index=dates,
            columns=tickers,
            dtype=float,
        )
        membership = pd.DataFrame(
            True,
            index=dates,
            columns=tickers,
        )
        forward_returns = pd.DataFrame(
            [np.arange(30), np.arange(30)],
            index=dates,
            columns=tickers,
            dtype=float,
        )

        signal, quantiles = prepare_factor_quantiles(factor, membership)
        statistics = aggregate_quantile_relationships(
            signal,
            quantiles,
            forward_returns,
        )
        relationships = compute_daily_relationship_metrics(
            signal,
            forward_returns,
        )

        self.assertEqual(statistics["signal_asset_count"][0], 0)
        self.assertEqual(statistics["return_asset_count"][0], 0)
        self.assertTrue(np.isnan(statistics["return_means"][0]).all())
        np.testing.assert_array_equal(
            statistics["counts"][1],
            np.repeat(3, 10),
        )
        self.assertEqual(statistics["signal_asset_count"][1], 30)
        self.assertEqual(statistics["return_asset_count"][1], 30)
        self.assertAlmostEqual(statistics["signal_means"][1, 0], 1.0)
        self.assertAlmostEqual(statistics["signal_means"][1, 9], 28.0)
        self.assertAlmostEqual(statistics["signal_medians"][1, 0], 1.0)
        self.assertAlmostEqual(statistics["return_means"][1, 0], 1.0)
        self.assertAlmostEqual(statistics["return_means"][1, 9], 28.0)
        self.assertAlmostEqual(statistics["return_medians"][1, 9], 28.0)
        self.assertAlmostEqual(relationships["spearman_ic"][1], 1.0)
        self.assertAlmostEqual(
            relationships["pearson_correlation"][1],
            1.0,
        )
        self.assertAlmostEqual(relationships["factor_beta"][1], 1.0)

    def test_daily_effects_keep_monotonic_and_tail_contrasts_separate(self):
        frame = pd.DataFrame(
            {
                "spearman_ic": [0.2],
                **{
                    f"q{quantile}_return_mean": [quantile / 100]
                    for quantile in range(1, 11)
                },
            }
        )

        effects = daily_effects(frame)

        self.assertAlmostEqual(effects["q10_minus_q1"].iloc[0], 0.09)
        self.assertAlmostEqual(
            effects["q10_minus_middle"].iloc[0],
            0.045,
        )
        self.assertAlmostEqual(
            effects["middle_minus_q1"].iloc[0],
            0.045,
        )
        self.assertAlmostEqual(
            effects["edges_minus_middle"].iloc[0],
            0.0,
        )

    def test_pattern_classification_accepts_negative_monotonic_shape(self):
        row = pd.Series(
            {
                "quantile_curve_rho": -0.95,
                "quantile_step_ratio": 0.80,
                "q10_minus_q1_mean": -0.03,
                "q10_minus_q1_hac_tstat": -3.0,
                "q10_minus_middle_mean": -0.02,
                "q10_minus_middle_hac_tstat": -2.5,
                "middle_minus_q1_mean": -0.01,
                "middle_minus_q1_hac_tstat": -2.0,
            }
        )

        pattern, direction, primary = classify_pattern(row)

        self.assertEqual(pattern, "negative_monotonic")
        self.assertEqual(direction, "negative")
        self.assertEqual(primary, "q10_minus_q1")


if __name__ == "__main__":
    unittest.main()
