import os
import sys
from datetime import datetime, timezone
from time import perf_counter

import pandas as pd


RESEARCH_LAYER_PATH = os.path.dirname(os.path.dirname(__file__))
if RESEARCH_LAYER_PATH not in sys.path:
    sys.path.insert(0, RESEARCH_LAYER_PATH)


from factor_overlap import run_factor_overlap
from Low_Volatility.config import (
    LOW_VOLATILITY_ANCHOR_BETA_NEUTRAL,
    LOW_VOLATILITY_ANCHOR_METHOD,
    LOW_VOLATILITY_ANCHOR_REBALANCE_DAYS,
    LOW_VOLATILITY_BENCHMARK_PATH,
    LOW_VOLATILITY_CACHE_MANIFEST_PATH,
    LOW_VOLATILITY_FACTOR_OVERLAP_PATH,
    LOW_VOLATILITY_PORTFOLIO_STATISTICS_PATH,
    LOW_VOLATILITY_REGIME_RESULTS_PATH,
    LOW_VOLATILITY_REPORT_PATH,
    LOW_VOLATILITY_RUN_METADATA_PATH,
    LOW_VOLATILITY_SECTOR_STATUS_PATH,
    LOW_VOLATILITY_WALK_FORWARD_PATHS_PATH,
    LOW_VOLATILITY_WALK_FORWARD_PERIODS_PATH,
    LOW_VOLATILITY_WALK_FORWARD_SUMMARY_PATH,
    LOW_VOLATILITY_WINDOW_SUMMARY_PATH,
    LOW_VOLATILITY_WINDOWS,
)
from Low_Volatility.research import (
    build_low_volatility_report,
    build_window_summary,
    create_low_volatility_figures,
    load_low_volatility_cache,
    load_low_volatility_candidates,
    load_low_volatility_factors,
    low_volatility_cache_is_valid,
    prepare_low_volatility_directories,
    save_low_volatility_cache,
)
from portfolio_engine import aggregate_calendar_phases, build_phase_paths
from portfolio_evaluation import benchmark_statistics, evaluate_portfolios
from regime_research import run_regime_analysis
from research_config import (
    AVAILABILITY_PATH,
    BETA_NEUTRAL_OPTIONS,
    CALENDAR_PHASES_PER_FREQUENCY,
    FACTOR_METADATA_PATH,
    MEMBERSHIP_PATH,
    PORTFOLIO_METHODS,
    REBALANCE_FREQUENCIES,
    RESEARCH_CODE_PATHS,
    RETURNS_PATH,
    RISK_FREE_RATE_PATH,
    SECTOR_HISTORY_PATH,
    SELECTION_CARDS_PATH,
    TRANSACTION_COST_BPS,
)
from research_data import (
    build_sector_matrix,
    load_research_data,
    load_risk_free_daily,
    load_sector_history,
)
from research_storage import (
    input_signature,
    save_csv,
    save_json,
    save_parquet,
    save_text,
)
from risk_exposure import (
    build_market_regimes,
    build_market_return,
    build_trailing_betas,
)
from walk_forward_research import run_walk_forward


def low_volatility_settings():
    return {
        "windows": LOW_VOLATILITY_WINDOWS,
        "anchor_method": LOW_VOLATILITY_ANCHOR_METHOD,
        "anchor_beta_neutral": LOW_VOLATILITY_ANCHOR_BETA_NEUTRAL,
        "anchor_rebalance_days": LOW_VOLATILITY_ANCHOR_REBALANCE_DAYS,
        "portfolio_methods": PORTFOLIO_METHODS,
        "beta_neutral_options": BETA_NEUTRAL_OPTIONS,
        "rebalance_frequencies": REBALANCE_FREQUENCIES,
        "calendar_phases_per_frequency": CALENDAR_PHASES_PER_FREQUENCY,
        "transaction_cost_bps": TRANSACTION_COST_BPS,
    }


def prepare_low_volatility_paths(
    returns,
    membership,
    availability,
    factors,
    candidates,
    sector_matrix,
):
    input_paths = [
        RETURNS_PATH,
        MEMBERSHIP_PATH,
        AVAILABILITY_PATH,
        RISK_FREE_RATE_PATH,
        FACTOR_METADATA_PATH,
        SELECTION_CARDS_PATH,
        SECTOR_HISTORY_PATH,
        *RESEARCH_CODE_PATHS,
        *candidates["factor_path"].tolist(),
    ]
    candidate_signature = candidates[
        ["factor_key", "window", "selection_horizon"]
    ].to_dict("records")
    signature, payload = input_signature(
        input_paths,
        low_volatility_settings(),
        candidates=candidate_signature,
    )
    if low_volatility_cache_is_valid(signature):
        print("Reuse valid Low Volatility portfolio cache")
        matrices, metadata, phase_stability = load_low_volatility_cache()
        return matrices, metadata, phase_stability, False

    market_return = build_market_return(returns, membership, availability)
    print("Build trailing point-in-time betas")
    betas = build_trailing_betas(returns, market_return)
    phase_matrices, phase_metadata = build_phase_paths(
        factors,
        candidates,
        returns,
        membership,
        availability,
        betas,
        sector_matrix,
    )
    matrices, metadata, phase_stability = aggregate_calendar_phases(
        phase_matrices,
        phase_metadata,
    )
    save_low_volatility_cache(
        matrices,
        metadata,
        phase_stability,
        signature,
        payload,
    )
    return matrices, metadata, phase_stability, True


def run_low_volatility_pipeline():
    start_time = perf_counter()
    prepare_low_volatility_directories()
    try:
        returns, membership, availability = load_research_data()
        candidates = load_low_volatility_candidates()
        factors = load_low_volatility_factors(
            candidates,
            returns.index,
            returns.columns,
        )
        risk_free = load_risk_free_daily(returns.index)
        market_return = build_market_return(returns, membership, availability)
        benchmarks = benchmark_statistics(
            market_return,
            risk_free["daily_rate"],
        )
        save_csv(benchmarks, LOW_VOLATILITY_BENCHMARK_PATH)

        factor_overlap = run_factor_overlap(
            factors,
            membership,
            availability,
        )
        save_csv(factor_overlap, LOW_VOLATILITY_FACTOR_OVERLAP_PATH)

        sectors, sector_status_data = load_sector_history()
        sector_matrix = build_sector_matrix(
            sectors,
            returns.index,
            returns.columns,
        )
        sector_status = pd.DataFrame([sector_status_data])
        save_csv(sector_status, LOW_VOLATILITY_SECTOR_STATUS_PATH)

        regimes = build_market_regimes(
            returns,
            membership,
            availability,
            market_return,
            risk_free,
        )
        matrices, metadata, phase_stability, cache_rebuilt = (
            prepare_low_volatility_paths(
                returns,
                membership,
                availability,
                factors,
                candidates,
                sector_matrix,
            )
        )
        statistics = evaluate_portfolios(
            matrices,
            metadata,
            market_return,
            risk_free["daily_rate"],
        )
        save_csv(statistics, LOW_VOLATILITY_PORTFOLIO_STATISTICS_PATH)

        walk_periods, walk_summary, walk_paths = run_walk_forward(
            matrices,
            metadata,
            risk_free["daily_rate"],
        )
        save_csv(walk_periods, LOW_VOLATILITY_WALK_FORWARD_PERIODS_PATH)
        save_csv(walk_summary, LOW_VOLATILITY_WALK_FORWARD_SUMMARY_PATH)
        save_parquet(
            walk_paths.astype("float32"),
            LOW_VOLATILITY_WALK_FORWARD_PATHS_PATH,
        )

        regime_results = run_regime_analysis(
            walk_paths,
            regimes,
            walk_summary,
        )
        save_csv(regime_results, LOW_VOLATILITY_REGIME_RESULTS_PATH)
        window_summary = build_window_summary(
            candidates,
            statistics,
            phase_stability,
            walk_summary,
            regime_results,
        )
        save_csv(window_summary, LOW_VOLATILITY_WINDOW_SUMMARY_PATH)
        figure_paths = create_low_volatility_figures(
            window_summary,
            statistics,
        )
        report = build_low_volatility_report(
            candidates,
            window_summary,
            statistics,
            benchmarks,
            sector_status,
            figure_paths,
        )
        save_text(report, LOW_VOLATILITY_REPORT_PATH)

        run_metadata = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "factor_windows": list(LOW_VOLATILITY_WINDOWS),
            "factor_count": len(candidates),
            "portfolio_path_count": metadata["path_key"].nunique(),
            "portfolio_cache_rebuilt": cache_rebuilt,
            "walk_forward_path_count": len(walk_summary),
            "figure_count": len(figure_paths),
            "sector_exposure_status": sector_status_data["status"],
            "cache_manifest": LOW_VOLATILITY_CACHE_MANIFEST_PATH,
        }
        save_json(run_metadata, LOW_VOLATILITY_RUN_METADATA_PATH)
        print("Low Volatility research is ready")
        print(f"Portfolio paths: {run_metadata['portfolio_path_count']}")
        print(f"Report: {LOW_VOLATILITY_REPORT_PATH}")
        return window_summary
    finally:
        elapsed = perf_counter() - start_time
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(
            "Low Volatility pipeline time: "
            f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"
        )


if __name__ == "__main__":
    run_low_volatility_pipeline()
