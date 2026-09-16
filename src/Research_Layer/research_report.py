import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from research_config import (
    PRIMARY_TRANSACTION_COST_BPS,
    RESEARCH_FIGURES_DIR,
    RESEARCH_SUMMARY_PATH,
)


def save_figure(figure, name):
    os.makedirs(RESEARCH_FIGURES_DIR, exist_ok=True)
    path = os.path.join(RESEARCH_FIGURES_DIR, name)
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def candidate_label(factor_key):
    family = factor_key.split("|", maxsplit=1)[0]
    labels = {
        "volatility_scaled_momentum": "Vol-Scaled Momentum",
        "short_term_reversal": "Short Reversal",
        "liquidity_change": "Liquidity Change",
        "low_volatility": "Low Volatility",
    }
    return labels.get(family, family.replace("_", " ").title())


def plot_research_summary(candidate_decisions, portfolio_statistics):
    decisions = candidate_decisions.copy()
    decisions["candidate"] = decisions["factor_key"].map(candidate_label)
    status_colors = {
        "ECONOMIC_LEAD": "#2F855A",
        "STATISTICAL_LEAD": "#805AD5",
        "REJECTED": "#C53030",
    }

    figure, axes = plt.subplots(1, 3, figsize=(17.5, 5.7))
    figure.suptitle("General Research Summary", fontsize=20, fontweight="bold")
    figure.text(
        0.5,
        0.91,
        (
            f"{len(decisions)} frozen leads  |  "
            f"{portfolio_statistics['path_key'].nunique()} portfolio implementations  |  "
            f"primary cost {PRIMARY_TRANSACTION_COST_BPS} bps"
        ),
        ha="center",
        color="#4A5568",
    )

    status_axis = axes[0]
    status_order = ("ECONOMIC_LEAD", "STATISTICAL_LEAD", "REJECTED")
    status_counts = decisions["final_status"].value_counts()
    values = [int(status_counts.get(status, 0)) for status in status_order]
    bars = status_axis.bar(
        [status.replace("_", "\n") for status in status_order],
        values,
        color=[status_colors[status] for status in status_order],
    )
    status_axis.bar_label(bars, padding=3, fontsize=12, fontweight="bold")
    status_axis.set_title("Candidate decisions", fontweight="bold")
    status_axis.set_ylabel("Candidates")
    status_axis.set_ylim(0, max(values) + 0.6)
    status_axis.spines[["top", "right"]].set_visible(False)
    status_axis.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    status_axis.set_axisbelow(True)

    return_axis = axes[1]
    ordered = decisions.sort_values("best_net_annualized_return")
    bars = return_axis.barh(
        ordered["candidate"],
        ordered["best_net_annualized_return"] * 100,
        color=[status_colors.get(status, "#718096") for status in ordered["final_status"]],
    )
    return_axis.bar_label(bars, fmt="%.2f%%", padding=3, fontsize=9)
    return_axis.axvline(0, color="black", linewidth=0.8)
    return_axis.set_title("Selected net annual return", fontweight="bold")
    return_axis.set_xlabel(f"Annualized return at {PRIMARY_TRANSACTION_COST_BPS} bps")
    return_axis.spines[["top", "right", "left"]].set_visible(False)
    return_axis.grid(axis="x", color="#E2E8F0", linewidth=0.8)
    return_axis.set_axisbelow(True)

    sharpe_axis = axes[2]
    x = np.arange(len(decisions))
    width = 0.36
    sharpe_axis.bar(
        x - width / 2,
        decisions["best_net_sharpe"],
        width,
        label="Full history",
        color="#2B6CB0",
    )
    sharpe_axis.bar(
        x + width / 2,
        decisions["best_long_wf_sharpe"],
        width,
        label="Long walk-forward",
        color="#DD6B20",
    )
    sharpe_axis.axhline(0, color="black", linewidth=0.8)
    sharpe_axis.set_xticks(x, decisions["candidate"], rotation=15, ha="right")
    sharpe_axis.set_title("Selected implementation Sharpe", fontweight="bold")
    sharpe_axis.legend(fontsize=8)
    sharpe_axis.spines[["top", "right"]].set_visible(False)
    sharpe_axis.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    sharpe_axis.set_axisbelow(True)

    figure.subplots_adjust(
        top=0.78,
        bottom=0.20,
        left=0.055,
        right=0.98,
        wspace=0.62,
    )
    os.makedirs(RESEARCH_FIGURES_DIR, exist_ok=True)
    figure.savefig(RESEARCH_SUMMARY_PATH, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return RESEARCH_SUMMARY_PATH


def plot_multiple_testing(summary):
    figure, axis = plt.subplots(figsize=(11, 5))
    axis.bar(summary["method"], summary["rejections"], color="#4472C4")
    axis.set_title("Discoveries under different multiple-testing rules")
    axis.set_ylabel("Rejected null hypotheses")
    axis.tick_params(axis="x", rotation=25)
    axis.grid(axis="y", alpha=0.25)
    return save_figure(figure, "multiple_testing_comparison.png")


def plot_cost_sensitivity(statistics):
    grouped = (
        statistics.groupby(["factor_key", "transaction_cost_bps"])["sharpe"]
        .median()
        .reset_index()
    )
    figure, axis = plt.subplots(figsize=(11, 6))
    for factor_key, data in grouped.groupby("factor_key"):
        axis.plot(
            data["transaction_cost_bps"],
            data["sharpe"],
            marker="o",
            label=factor_key,
        )
    axis.axhline(0, color="black", linewidth=1)
    axis.set_title("Median implementation Sharpe after transaction costs")
    axis.set_xlabel("One-way transaction cost, bps")
    axis.set_ylabel("Median Sharpe")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.25)
    return save_figure(figure, "transaction_cost_sensitivity.png")


def plot_turnover_sharpe(statistics):
    data = statistics.loc[
        statistics["transaction_cost_bps"].eq(PRIMARY_TRANSACTION_COST_BPS)
    ]
    figure, axis = plt.subplots(figsize=(10, 6))
    colors = {"market_neutral": "#4472C4", "long_only": "#ED7D31"}
    for portfolio_type, group in data.groupby("portfolio_type"):
        axis.scatter(
            group["annualized_turnover"],
            group["sharpe"],
            alpha=0.65,
            s=30,
            label=portfolio_type,
            color=colors.get(portfolio_type),
        )
    axis.axhline(0, color="black", linewidth=1)
    axis.set_title(
        f"Turnover and net Sharpe at {PRIMARY_TRANSACTION_COST_BPS} bps"
    )
    axis.set_xlabel("Annualized one-way turnover")
    axis.set_ylabel("Net Sharpe")
    axis.legend()
    axis.grid(alpha=0.25)
    return save_figure(figure, "turnover_vs_sharpe.png")


def plot_walk_forward_paths(summary, paths):
    if summary.empty:
        return None
    selected = (
        summary.sort_values("stitched_oos_sharpe", ascending=False)
        .groupby(["walk_forward_scheme", "factor_key"], as_index=False)
        .first()
    )
    figure, axis = plt.subplots(figsize=(12, 6))
    for row in selected.itertuples(index=False):
        values = paths[row.walk_key].dropna()
        if values.empty:
            continue
        wealth = (1 + values).cumprod()
        axis.plot(
            wealth.index,
            wealth,
            label=f"{row.walk_forward_scheme}: {row.factor_key}",
        )
    axis.axhline(1, color="black", linewidth=1)
    axis.set_title(
        "Best displayed post-selection walk-forward path per factor"
    )
    axis.set_ylabel("Growth of 1")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.25)
    return save_figure(figure, "walk_forward_paths.png")


def plot_regime_comparison(regime_results, walk_forward_summary):
    if regime_results.empty or walk_forward_summary.empty:
        return None
    top_path = walk_forward_summary.sort_values(
        "stitched_oos_sharpe",
        ascending=False,
    ).iloc[0]["walk_key"]
    data = regime_results.loc[regime_results["walk_key"].eq(top_path)]
    if data.empty:
        return None
    labels = (
        data["regime_variable"].astype(str)
        + "\n"
        + data["regime_state"].astype(str)
    )
    figure, axis = plt.subplots(figsize=(12, 5))
    axis.bar(labels, data["annualized_return_approx"], color="#70AD47")
    axis.axhline(0, color="black", linewidth=1)
    axis.set_title("Top displayed walk-forward path across market regimes")
    axis.set_ylabel("Approximate annualized mean return")
    axis.tick_params(axis="x", rotation=35)
    axis.grid(axis="y", alpha=0.25)
    return save_figure(figure, "regime_comparison.png")


def plot_factor_overlap(factor_overlap):
    if factor_overlap.empty:
        return None
    names = sorted(
        set(factor_overlap["factor_left"])
        | set(factor_overlap["factor_right"])
    )
    matrix = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
    for row in factor_overlap.itertuples(index=False):
        matrix.loc[row.factor_left, row.factor_right] = (
            row.mean_daily_rank_correlation
        )
        matrix.loc[row.factor_right, row.factor_left] = (
            row.mean_daily_rank_correlation
        )
    figure, axis = plt.subplots(figsize=(9, 7))
    image = axis.imshow(matrix, cmap="RdBu", vmin=-1, vmax=1)
    short_names = [name.split("|", maxsplit=1)[0] for name in names]
    axis.set_xticks(range(len(names)), short_names, rotation=35, ha="right")
    axis.set_yticks(range(len(names)), short_names)
    for row in range(len(names)):
        for column in range(len(names)):
            axis.text(
                column,
                row,
                f"{matrix.iloc[row, column]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    figure.colorbar(image, ax=axis, label="Mean daily rank correlation")
    axis.set_title("Candidate factor overlap")
    return save_figure(figure, "factor_overlap.png")


def create_research_figures(
    candidate_decisions,
    multiple_testing_summary,
    portfolio_statistics,
    walk_forward_summary,
    walk_forward_paths,
    regime_results,
    factor_overlap,
):
    paths = [
        plot_research_summary(candidate_decisions, portfolio_statistics),
        plot_multiple_testing(multiple_testing_summary),
        plot_cost_sensitivity(portfolio_statistics),
        plot_turnover_sharpe(portfolio_statistics),
        plot_walk_forward_paths(walk_forward_summary, walk_forward_paths),
        plot_regime_comparison(regime_results, walk_forward_summary),
        plot_factor_overlap(factor_overlap),
    ]
    return [path for path in paths if path is not None]


def markdown_table(frame, columns, limit=15):
    if frame.empty:
        return "No rows."
    frame = frame.loc[:, columns].head(limit).copy()
    for column in frame.select_dtypes(include="number").columns:
        frame[column] = frame[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.4f}"
        )
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def relative_figure_path(path):
    return "Figures/" + os.path.basename(path)


def build_research_report(
    candidates,
    candidate_decisions,
    benchmark_statistics,
    multiple_testing_summary,
    portfolio_statistics,
    phase_stability,
    walk_forward_summary,
    risk_summary,
    sector_status,
    regime_results,
    factor_overlap,
    figure_paths,
):
    primary = portfolio_statistics.loc[
        portfolio_statistics["transaction_cost_bps"].eq(
            PRIMARY_TRANSACTION_COST_BPS
        )
    ].sort_values("sharpe", ascending=False)
    walk = walk_forward_summary.sort_values(
        "stitched_oos_sharpe",
        ascending=False,
    )
    lines = [
        "# Research Layer Report",
        "",
        "![General Research summary](Figures/general_research_summary.png)",
        "",
        "## Scope",
        "",
        f"- Frozen factor leads: `{len(candidates)}`.",
        f"- Portfolio implementations: `{primary['path_key'].nunique()}`.",
        f"- Transaction-cost assumptions: `{sorted(portfolio_statistics['transaction_cost_bps'].unique().tolist())}` bps.",
        f"- Primary reporting cost: `{PRIMARY_TRANSACTION_COST_BPS}` bps.",
        "- Walk-forward status: post-selection historical simulation, not a genuinely untouched final test.",
        "",
        "## Frozen Candidates",
        "",
        markdown_table(
            candidates,
            [
                "factor_key",
                "selection_horizon",
                "selection_evidence",
                "selection_pattern",
                "selection_status",
            ],
        ),
        "",
        "## Final Candidate Decisions",
        "",
        "The labels apply the declared statistical and economic rules. `VALIDATED_ALPHA` is intentionally unavailable because no untouched final sample remains after candidate discovery.",
        "",
        markdown_table(
            candidate_decisions,
            [
                "factor_key",
                "final_status",
                "best_method",
                "best_rebalance_days",
                "best_net_annualized_return",
                "best_net_sharpe",
                "best_alpha_hac_tstat",
                "best_long_wf_sharpe",
            ],
        ),
        "",
        "## Benchmarks",
        "",
        markdown_table(
            benchmark_statistics,
            [
                "benchmark",
                "annualized_return",
                "annualized_volatility",
                "sharpe",
                "maximum_drawdown",
            ],
        ),
        "",
        "## Multiple Testing Sensitivity",
        "",
        "Global FDR remains the original confirmatory result. Within-group values are reported as sensitivity diagnostics and do not replace it after seeing the data.",
        "",
        markdown_table(
            multiple_testing_summary,
            [
                "method",
                "rejections",
                "economic_rejections",
                "ic_rejections",
                "interpretation",
            ],
        ),
        "",
        "## Candidate Factor Overlap",
        "",
        "Daily cross-sectional rank correlation shows whether two candidate formulas mostly encode the same stock ordering.",
        "",
        markdown_table(
            factor_overlap.sort_values(
                "mean_absolute_daily_rank_correlation",
                ascending=False,
            ),
            [
                "factor_left",
                "factor_right",
                "mean_daily_rank_correlation",
                "mean_absolute_daily_rank_correlation",
                "high_absolute_overlap_rate",
            ],
            limit=10,
        ),
        "",
        "## Full-History Portfolio Implementations",
        "",
        "These results are descriptive because both candidates and implementations are visible on the same historical sample.",
        "",
        markdown_table(
            primary,
            [
                "factor_key",
                "method",
                "beta_neutral",
                "rebalance_days",
                "annualized_return",
                "sharpe",
                "maximum_drawdown",
                "annualized_turnover",
                "alpha_hac_tstat",
            ],
        ),
        "",
        "## Walk-Forward Behaviour",
        "",
        "Each implementation is kept fixed. Only the sign of a market-neutral spread is chosen inside either the preceding 18-month or four-year training window and then applied to the following six- or twelve-month OOS period. No implementation winner is silently removed from the output.",
        "",
        markdown_table(
            walk,
            [
                "factor_key",
                "method",
                "beta_neutral",
                "rebalance_days",
                "complete_oos_periods",
                "positive_oos_period_rate",
                "stitched_oos_annualized_return",
                "stitched_oos_sharpe",
                "orientation_changes",
            ],
        ),
        "",
        "## Risk and Data Diagnostics",
        "",
        f"- Sector exposure status: `{sector_status.iloc[0]['status']}` — {sector_status.iloc[0]['reason']}",
        "- Missing returns held by a portfolio are reported as unpriced weight; they are never silently presented as verified zero returns.",
        "- Beta-neutralization uses trailing 252-day betas shifted by one day.",
        "- Long-only Sharpe is calculated over the risk-free rate. Market-neutral Sharpe uses the self-financing spread return convention.",
        "",
        markdown_table(
            risk_summary.sort_values(
                "maximum_absolute_estimated_beta",
                ascending=False,
            ),
            [
                "factor_key",
                "method",
                "beta_neutral",
                "rebalance_days",
                "average_estimated_beta",
                "maximum_absolute_estimated_beta",
                "average_gross_exposure",
                "average_net_exposure",
                "maximum_position_weight",
                "maximum_unpriced_weight",
            ],
            limit=10,
        ),
        "",
        "## Calendar-Phase Stability",
        "",
        markdown_table(
            phase_stability.sort_values("phase_sharpe_mean", ascending=False),
            [
                "path_key",
                "phase_count",
                "phase_sharpe_mean",
                "phase_sharpe_min",
                "phase_sharpe_max",
                "phase_sharpe_std",
            ],
            limit=10,
        ),
        "",
        "## Interpretation Boundary",
        "",
        "- A strong full-history path is not final evidence because the candidate shortlist was obtained from the same complete history.",
        "- Hierarchical and within-family FDR are sensitivity checks, not permission to ignore the global FDR result.",
        "- A candidate requires coherent walk-forward returns, tolerable turnover and costs, controlled risk exposure, and no dependence on one market regime.",
        "- Remaining Yahoo historical-data limitations continue to apply.",
        "",
        "## Figures",
        "",
    ]
    for path in figure_paths:
        if os.path.basename(path) == "general_research_summary.png":
            continue
        title = os.path.splitext(os.path.basename(path))[0].replace("_", " ").title()
        lines.extend(
            [
                f"### {title}",
                "",
                f"![{title}]({relative_figure_path(path)})",
                "",
            ]
        )
    return "\n".join(lines)
