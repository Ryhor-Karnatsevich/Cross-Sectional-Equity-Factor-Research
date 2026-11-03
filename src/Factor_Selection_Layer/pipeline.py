import argparse
import json
from datetime import datetime, timezone
from time import perf_counter

from classifier_validation import run_classifier_validation
from hypothesis_analysis import build_hypothesis_metrics, load_saved_hypothesis_metrics
from pattern_classification import classify_hypotheses
from quantile_analysis import run_quantile_analysis
from selection_config import (
    ACTIVE_FACTOR_KEYS,
    EFFECT_TESTS_PATH,
    HYPOTHESIS_CARDS_PATH,
    MULTIPLE_TESTING_ALPHA,
    QUANTILE_CURVES_PATH,
    SELECTION_REPORT_PATH,
    SELECTION_RUN_METADATA_PATH,
    TIME_STABILITY_PATH,
)
from selection_report import build_selection_report, create_selection_figures
from selection_storage import (
    prepare_selection_directories,
    quantile_cache_is_valid,
    save_csv,
    save_json,
    save_parquet,
    save_text,
)


# -------------------------
# QUANTILE DATA FOUNDATION
def prepare_quantile_data():
    if quantile_cache_is_valid():
        print("Reuse valid daily_quantile_results.parquet")
        return False

    print("Quantile cache missing or outdated -> rebuilding")
    run_quantile_analysis()
    return True


# -------------------------
# HYPOTHESIS CLASSIFICATION
def run_factor_classification(correction_only=False):
    classifier_validation = run_classifier_validation()
    if correction_only:
        cards, effect_tests, curves, time_stability, factor_count = (
            load_saved_hypothesis_metrics()
        )
    else:
        cards, effect_tests, curves, time_stability, factor_count = (
            build_hypothesis_metrics()
        )
    cards, effect_tests = classify_hypotheses(
        cards,
        effect_tests,
        factor_count,
    )
    save_csv(cards, HYPOTHESIS_CARDS_PATH)
    save_csv(effect_tests, EFFECT_TESTS_PATH)
    if not correction_only:
        save_csv(curves, QUANTILE_CURVES_PATH)
        save_parquet(time_stability, TIME_STABILITY_PATH)
    figure_paths = create_selection_figures(
        cards,
        effect_tests,
        curves,
        time_stability,
    )
    report = build_selection_report(cards, effect_tests, figure_paths)
    save_text(report, SELECTION_REPORT_PATH)
    return (
        cards,
        effect_tests,
        curves,
        time_stability,
        figure_paths,
        classifier_validation,
    )


# -------------------------
# COMPLETE FACTOR SELECTION LAYER
def run_pipeline(correction_only=False):
    start_time = perf_counter()
    prepare_selection_directories()

    try:
        if correction_only:
            print("Correction-only mode: reuse saved statistics; skip factor analysis and HAC")
            with open(SELECTION_RUN_METADATA_PATH, encoding="utf-8") as file:
                previous_run = json.load(file)
            statistics_created = previous_run.get(
                "hypothesis_metrics_created_at_utc", previous_run["created_at_utc"]
            )
            quantile_data_rebuilt = False
        else:
            quantile_data_rebuilt = prepare_quantile_data()
            statistics_created = datetime.now(timezone.utc).isoformat()
        (
            cards,
            effect_tests,
            curves,
            time_stability,
            figure_paths,
            classifier_validation,
        ) = run_factor_classification(correction_only=correction_only)
        full_scope = bool(effect_tests["full_research_scope"].iloc[0])
        run_metadata = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "hypothesis_metrics_created_at_utc": statistics_created,
            "correction_only": correction_only,
            "statistical_metrics_reused": correction_only,
            "active_factor_keys": (
                list(ACTIVE_FACTOR_KEYS)
                if ACTIVE_FACTOR_KEYS is not None
                else None
            ),
            "factor_configurations_analyzed": cards[
                "factor_key"
            ].nunique(),
            "hypotheses_analyzed": cards["hypothesis_key"].nunique(),
            "effect_tests_analyzed": len(effect_tests),
            "multiple_testing_method": "benjamini_hochberg",
            "multiple_testing_scope": "within_effect",
            "multiple_testing_alpha": MULTIPLE_TESTING_ALPHA,
            "effect_family_test_counts": effect_tests.groupby("effect").size().to_dict(),
            "full_448_hypothesis_scope": full_scope,
            "quantile_data_rebuilt": quantile_data_rebuilt,
            "figures_created": len(figure_paths),
            "classifier_validation_passed": bool(
                classifier_validation["passed"].all()
            ),
            "pattern_counts": cards["pattern"].value_counts().to_dict(),
            "evidence_status_counts": cards[
                "evidence_status"
            ].value_counts().to_dict(),
        }
        save_json(run_metadata, SELECTION_RUN_METADATA_PATH)
        print("Factor classification is ready")
        print(
            "Factors analyzed: "
            f"{run_metadata['factor_configurations_analyzed']}"
        )
        print(f"Hypotheses analyzed: {run_metadata['hypotheses_analyzed']}")
        print(f"Cards: {HYPOTHESIS_CARDS_PATH}")
        print(f"Report: {SELECTION_REPORT_PATH}")
        return cards
    finally:
        elapsed_seconds = perf_counter() - start_time
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(
            "Factor Selection pipeline time: "
            f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Factor Selection pipeline")
    parser.add_argument(
        "--correction-only", action="store_true",
        help="Reuse saved statistics; update BH, candidate labels and reports only",
    )
    run_pipeline(correction_only=parser.parse_args().correction_only)
