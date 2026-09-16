import json
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from multiple_testing_research import bh_values
from portfolio_engine import MATRIX_NAMES
from Low_Volatility.config import (
    FACTOR_MATRIX_DIR,
    FACTOR_METADATA_PATH,
    LOW_VOLATILITY_ANCHOR_BETA_NEUTRAL,
    LOW_VOLATILITY_ANCHOR_METHOD,
    LOW_VOLATILITY_ANCHOR_REBALANCE_DAYS,
    LOW_VOLATILITY_CACHE_DIR,
    LOW_VOLATILITY_CACHE_MANIFEST_PATH,
    LOW_VOLATILITY_FIGURES_DIR,
    LOW_VOLATILITY_MIN_25BPS_RETURN,
    LOW_VOLATILITY_MIN_ALPHA_TSTAT,
    LOW_VOLATILITY_MIN_LONG_WF_POSITIVE_RATE,
    LOW_VOLATILITY_MIN_LONG_WF_SHARPE,
    LOW_VOLATILITY_MIN_NEIGHBOUR_SUPPORT,
    LOW_VOLATILITY_MIN_NET_SHARPE,
    LOW_VOLATILITY_MIN_PHASE_RETURN,
    LOW_VOLATILITY_MIN_REGIME_RETURN,
    LOW_VOLATILITY_MIN_SHORT_WF_POSITIVE_RATE,
    LOW_VOLATILITY_MIN_SHORT_WF_SHARPE,
    LOW_VOLATILITY_PHASE_STABILITY_PATH,
    LOW_VOLATILITY_PORTFOLIO_METADATA_PATH,
    LOW_VOLATILITY_RESULTS_DIR,
    LOW_VOLATILITY_SELECTION_HORIZON,
    LOW_VOLATILITY_WINDOWS,
    PRIMARY_TRANSACTION_COST_BPS,
    SELECTION_CARDS_PATH,
)
from research_data import read_matrix
from research_report import markdown_table
from research_storage import save_csv, save_json, save_parquet


LOW_VOLATILITY_CACHE_PATHS = {
    name: os.path.join(LOW_VOLATILITY_CACHE_DIR, f"{name}.parquet")
    for name in MATRIX_NAMES
}


def prepare_low_volatility_directories():
    os.makedirs(LOW_VOLATILITY_CACHE_DIR, exist_ok=True)
    os.makedirs(LOW_VOLATILITY_RESULTS_DIR, exist_ok=True)
    os.makedirs(LOW_VOLATILITY_FIGURES_DIR, exist_ok=True)


def load_low_volatility_candidates():
    metadata = pd.read_csv(FACTOR_METADATA_PATH)
    metadata = metadata.loc[metadata["family"].eq("low_volatility")].copy()
    metadata["window"] = metadata["parameters"].map(
        lambda value: int(json.loads(value)["window"])
    )
    metadata = metadata.loc[
        metadata["window"].isin(LOW_VOLATILITY_WINDOWS)
    ].copy()

    found = set(metadata["window"])
    expected = set(LOW_VOLATILITY_WINDOWS)
    if found != expected or metadata["window"].duplicated().any():
        raise ValueError(
            "Low Volatility matrices do not match the declared windows: "
            f"expected={sorted(expected)}, found={sorted(found)}"
        )

    cards = pd.read_csv(SELECTION_CARDS_PATH)
    cards = cards.loc[
        cards["horizon_days"].eq(LOW_VOLATILITY_SELECTION_HORIZON),
        [
            "factor_key",
            "pattern",
            "pattern_direction",
            "evidence_status",
            "primary_effect",
            "primary_effect_mean",
            "primary_effect_hac_tstat",
        ],
    ]
    if cards["factor_key"].duplicated().any():
        raise ValueError("Duplicated Low Volatility selection cards")

    candidates = metadata.merge(
        cards,
        left_on="key",
        right_on="factor_key",
        how="left",
        validate="one_to_one",
    )
    if candidates["pattern"].isna().any():
        raise ValueError("Missing 63-day Selection card for Low Volatility")

    candidates["factor_key"] = candidates["key"]
    candidates["selection_horizon"] = LOW_VOLATILITY_SELECTION_HORIZON
    candidates["selection_evidence"] = "low_volatility_family_sensitivity"
    candidates["selection_pattern"] = candidates["pattern"]
    candidates["selection_status"] = candidates["evidence_status"]
    candidates["factor_path"] = candidates["path"].map(os.path.abspath)

    allowed_root = os.path.abspath(FACTOR_MATRIX_DIR)
    for path in candidates["factor_path"]:
        if os.path.commonpath([path, allowed_root]) != allowed_root:
            raise ValueError(f"Factor path is outside Factor Layer: {path}")

    return candidates.sort_values("window").reset_index(drop=True)


def load_low_volatility_factors(candidates, index, columns):
    return {
        row.factor_key: read_matrix(row.factor_path).reindex(
            index=index,
            columns=columns,
        )
        for row in candidates.itertuples(index=False)
    }


def low_volatility_cache_is_valid(signature):
    if not os.path.exists(LOW_VOLATILITY_CACHE_MANIFEST_PATH):
        return False
    with open(
        LOW_VOLATILITY_CACHE_MANIFEST_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        manifest = json.load(file)
    required = [
        LOW_VOLATILITY_PORTFOLIO_METADATA_PATH,
        LOW_VOLATILITY_PHASE_STABILITY_PATH,
        *LOW_VOLATILITY_CACHE_PATHS.values(),
    ]
    return manifest.get("signature") == signature and all(
        os.path.exists(path) for path in required
    )


def save_low_volatility_cache(
    matrices,
    metadata,
    phase_stability,
    signature,
    signature_payload,
):
    for name, path in LOW_VOLATILITY_CACHE_PATHS.items():
        save_parquet(matrices[name].astype("float32"), path)
    save_csv(metadata, LOW_VOLATILITY_PORTFOLIO_METADATA_PATH)
    save_csv(phase_stability, LOW_VOLATILITY_PHASE_STABILITY_PATH)
    save_json(
        {
            "signature": signature,
            "inputs": signature_payload,
            "path_count": int(metadata["path_key"].nunique()),
            "dates": int(len(matrices["gross_returns"])),
        },
        LOW_VOLATILITY_CACHE_MANIFEST_PATH,
    )


def load_low_volatility_cache():
    matrices = {
        name: pd.read_parquet(path)
        for name, path in LOW_VOLATILITY_CACHE_PATHS.items()
    }
    metadata = pd.read_csv(LOW_VOLATILITY_PORTFOLIO_METADATA_PATH)
    phase_stability = pd.read_csv(LOW_VOLATILITY_PHASE_STABILITY_PATH)
    return matrices, metadata, phase_stability


def matching_anchor(frame):
    return frame.loc[
        frame["method"].eq(LOW_VOLATILITY_ANCHOR_METHOD)
        & frame["beta_neutral"].eq(
            LOW_VOLATILITY_ANCHOR_BETA_NEUTRAL
        )
        & frame["rebalance_days"].eq(
            LOW_VOLATILITY_ANCHOR_REBALANCE_DAYS
        )
    ]


def one_row(frame, description):
    if len(frame) != 1:
        raise ValueError(f"Expected one {description} row, found {len(frame)}")
    return frame.iloc[0]


def build_window_summary(
    candidates,
    portfolio_statistics,
    phase_stability,
    walk_forward_summary,
    regime_results,
):
    rows = []
    anchor_statistics = matching_anchor(portfolio_statistics)
    anchor_walk = matching_anchor(walk_forward_summary)
    anchor_regimes = matching_anchor(regime_results)

    for candidate in candidates.itertuples(index=False):
        factor_stats = anchor_statistics.loc[
            anchor_statistics["factor_key"].eq(candidate.factor_key)
        ]
        primary = one_row(
            factor_stats.loc[
                factor_stats["transaction_cost_bps"].eq(
                    PRIMARY_TRANSACTION_COST_BPS
                )
            ],
            "primary-cost anchor",
        )
        high_cost = one_row(
            factor_stats.loc[factor_stats["transaction_cost_bps"].eq(25)],
            "25-bps anchor",
        )
        phase = one_row(
            phase_stability.loc[
                phase_stability["path_key"].eq(primary["path_key"])
            ],
            "calendar-phase anchor",
        )
        factor_walk = anchor_walk.loc[
            anchor_walk["factor_key"].eq(candidate.factor_key)
        ]
        long_walk = one_row(
            factor_walk.loc[
                factor_walk["walk_forward_scheme"].eq("long")
            ],
            "long walk-forward anchor",
        )
        short_walk = one_row(
            factor_walk.loc[
                factor_walk["walk_forward_scheme"].eq("short")
            ],
            "short walk-forward anchor",
        )
        factor_regimes = anchor_regimes.loc[
            anchor_regimes["factor_key"].eq(candidate.factor_key)
            & anchor_regimes["walk_forward_scheme"].eq("long")
        ]
        if factor_regimes.empty:
            minimum_regime_return = np.nan
            weakest_regime = None
        else:
            weakest = factor_regimes.sort_values(
                "annualized_return_approx"
            ).iloc[0]
            minimum_regime_return = weakest["annualized_return_approx"]
            weakest_regime = (
                f"{weakest['regime_variable']}={weakest['regime_state']}"
            )

        row = {
            "factor_key": candidate.factor_key,
            "window": int(candidate.window),
            "selection_pattern": candidate.selection_pattern,
            "selection_status": candidate.selection_status,
            "net_annualized_return_10bps": primary["annualized_return"],
            "net_sharpe_10bps": primary["sharpe"],
            "alpha_hac_tstat_10bps": primary["alpha_hac_tstat"],
            "alpha_raw_p_value_10bps": primary["alpha_raw_p_value"],
            "regression_beta_10bps": primary["regression_beta"],
            "average_estimated_beta_10bps": primary[
                "average_estimated_beta"
            ],
            "maximum_drawdown_10bps": primary["maximum_drawdown"],
            "annualized_turnover": primary["annualized_turnover"],
            "average_holding_count": primary["average_holding_count"],
            "maximum_position_weight": primary["maximum_position_weight"],
            "net_annualized_return_25bps": high_cost["annualized_return"],
            "phase_annual_return_min": phase["phase_annual_return_min"],
            "phase_sharpe_min": phase["phase_sharpe_min"],
            "long_wf_annualized_return": long_walk[
                "stitched_oos_annualized_return"
            ],
            "long_wf_sharpe": long_walk["stitched_oos_sharpe"],
            "long_wf_positive_period_rate": long_walk[
                "positive_oos_period_rate"
            ],
            "short_wf_annualized_return": short_walk[
                "stitched_oos_annualized_return"
            ],
            "short_wf_sharpe": short_walk["stitched_oos_sharpe"],
            "short_wf_positive_period_rate": short_walk[
                "positive_oos_period_rate"
            ],
            "minimum_regime_annualized_return": minimum_regime_return,
            "weakest_regime": weakest_regime,
        }
        row.update(
            {
                "pass_positive_net_return": (
                    row["net_annualized_return_10bps"] > 0
                ),
                "pass_net_sharpe": (
                    row["net_sharpe_10bps"]
                    >= LOW_VOLATILITY_MIN_NET_SHARPE
                ),
                "pass_alpha_tstat": (
                    row["alpha_hac_tstat_10bps"]
                    >= LOW_VOLATILITY_MIN_ALPHA_TSTAT
                ),
                "pass_25bps_return": (
                    row["net_annualized_return_25bps"]
                    > LOW_VOLATILITY_MIN_25BPS_RETURN
                ),
                "pass_calendar_phases": (
                    row["phase_annual_return_min"]
                    > LOW_VOLATILITY_MIN_PHASE_RETURN
                ),
                "pass_long_walk_forward": (
                    row["long_wf_sharpe"]
                    >= LOW_VOLATILITY_MIN_LONG_WF_SHARPE
                    and row["long_wf_positive_period_rate"]
                    >= LOW_VOLATILITY_MIN_LONG_WF_POSITIVE_RATE
                ),
                "pass_short_walk_forward": (
                    row["short_wf_sharpe"]
                    > LOW_VOLATILITY_MIN_SHORT_WF_SHARPE
                    and row["short_wf_positive_period_rate"]
                    >= LOW_VOLATILITY_MIN_SHORT_WF_POSITIVE_RATE
                ),
                "pass_market_regimes": (
                    pd.notna(row["minimum_regime_annualized_return"])
                    and row["minimum_regime_annualized_return"]
                    > LOW_VOLATILITY_MIN_REGIME_RETURN
                ),
            }
        )
        rows.append(row)

    summary = pd.DataFrame(rows).sort_values("window").reset_index(drop=True)
    alpha_fdr = bh_values(summary["alpha_raw_p_value_10bps"])
    summary["alpha_bh_q_value_10bps"] = alpha_fdr["q_value"]
    summary["pass_alpha_fdr"] = alpha_fdr["rejected"].astype(bool)
    core_columns = [
        "pass_positive_net_return",
        "pass_net_sharpe",
        "pass_25bps_return",
        "pass_calendar_phases",
        "pass_long_walk_forward",
        "pass_market_regimes",
    ]
    summary["core_economic_pass"] = summary[core_columns].all(axis=1)

    support = []
    for position in range(len(summary)):
        neighbours = [
            neighbour
            for neighbour in (position - 1, position + 1)
            if 0 <= neighbour < len(summary)
        ]
        support.append(
            int(summary.loc[neighbours, "core_economic_pass"].sum())
        )
    summary["neighbour_support_count"] = support
    summary["pass_neighbour_support"] = (
        summary["neighbour_support_count"]
        >= LOW_VOLATILITY_MIN_NEIGHBOUR_SUPPORT
    )
    declared = [
        *core_columns,
        "pass_alpha_tstat",
        "pass_alpha_fdr",
        "pass_short_walk_forward",
        "pass_neighbour_support",
    ]
    summary["passed_declared_checks"] = summary[declared].sum(axis=1)
    summary["all_declared_checks_pass"] = summary[declared].all(axis=1)
    summary["research_status"] = "NOT_SUPPORTED"
    summary.loc[
        summary["core_economic_pass"]
        & ~summary["pass_neighbour_support"],
        "research_status",
    ] = "ISOLATED_RESULT"
    summary.loc[
        summary["core_economic_pass"]
        & summary["pass_neighbour_support"],
        "research_status",
    ] = "ROBUST_ECONOMIC_LEAD"
    summary.loc[
        summary["all_declared_checks_pass"],
        "research_status",
    ] = "STRONG_POST_SELECTION_LEAD"
    return summary


def save_low_volatility_figure(figure, name):
    path = os.path.join(LOW_VOLATILITY_FIGURES_DIR, name)
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def create_low_volatility_figures(summary, portfolio_statistics):
    paths = []

    figure, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    axes[0].plot(
        summary["window"],
        summary["net_annualized_return_10bps"],
        marker="o",
    )
    axes[0].axhline(0, color="black", linewidth=1)
    axes[0].set_ylabel("Net annualized return")
    axes[0].grid(alpha=0.25)
    axes[1].plot(
        summary["window"],
        summary["net_sharpe_10bps"],
        marker="o",
        color="#ED7D31",
    )
    axes[1].axhline(LOW_VOLATILITY_MIN_NET_SHARPE, color="black", linewidth=1)
    axes[1].set_xlabel("Volatility lookback, trading days")
    axes[1].set_ylabel("Net Sharpe")
    axes[1].grid(alpha=0.25)
    figure.suptitle("Low Volatility anchor across lookback windows")
    paths.append(save_low_volatility_figure(figure, "window_sensitivity.png"))

    figure, axis = plt.subplots(figsize=(11, 6))
    axis.plot(
        summary["window"],
        summary["long_wf_sharpe"],
        marker="o",
        label="4y train / 1y OOS",
    )
    axis.plot(
        summary["window"],
        summary["short_wf_sharpe"],
        marker="o",
        label="18m train / 6m OOS",
    )
    axis.axhline(0, color="black", linewidth=1)
    axis.set_xlabel("Volatility lookback, trading days")
    axis.set_ylabel("Stitched OOS Sharpe")
    axis.set_title("Walk-forward behaviour by lookback window")
    axis.legend()
    axis.grid(alpha=0.25)
    paths.append(save_low_volatility_figure(figure, "walk_forward_windows.png"))

    anchor = matching_anchor(portfolio_statistics)
    figure, axis = plt.subplots(figsize=(11, 6))
    for factor_key, group in anchor.groupby("factor_key"):
        window = int(factor_key.split("|")[-1].removesuffix("d"))
        group = group.sort_values("transaction_cost_bps")
        axis.plot(
            group["transaction_cost_bps"],
            group["sharpe"],
            marker="o",
            label=f"{window}d",
        )
    axis.axhline(0, color="black", linewidth=1)
    axis.set_xlabel("One-way transaction cost, bps")
    axis.set_ylabel("Sharpe")
    axis.set_title("Low Volatility anchor transaction-cost sensitivity")
    axis.legend(ncol=2)
    axis.grid(alpha=0.25)
    paths.append(save_low_volatility_figure(figure, "cost_sensitivity.png"))

    check_columns = [
        column for column in summary.columns if column.startswith("pass_")
    ]
    values = summary[check_columns].astype(int).to_numpy()
    figure, axis = plt.subplots(figsize=(13, 5))
    axis.imshow(values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    axis.set_xticks(
        range(len(check_columns)),
        [column.removeprefix("pass_") for column in check_columns],
        rotation=35,
        ha="right",
    )
    axis.set_yticks(range(len(summary)), summary["window"].astype(str) + "d")
    axis.set_title("Declared Low Volatility checks")
    paths.append(save_low_volatility_figure(figure, "declared_checks.png"))
    return paths


def build_low_volatility_report(
    candidates,
    summary,
    portfolio_statistics,
    benchmarks,
    sector_status,
    figure_paths,
):
    primary = portfolio_statistics.loc[
        portfolio_statistics["transaction_cost_bps"].eq(
            PRIMARY_TRANSACTION_COST_BPS
        )
        & portfolio_statistics["portfolio_type"].eq("market_neutral")
    ].sort_values("sharpe", ascending=False)
    strong = summary.loc[
        summary["research_status"].eq("STRONG_POST_SELECTION_LEAD")
    ]
    robust = summary.loc[
        summary["research_status"].eq("ROBUST_ECONOMIC_LEAD")
    ]
    if not strong.empty:
        conclusion = (
            "At least one window passed every declared check, but remains a "
            "post-selection lead rather than validated alpha."
        )
    elif not robust.empty:
        conclusion = (
            "The family contains economically robust neighbouring windows, "
            "but no window passed every statistical and short-term check."
        )
    else:
        conclusion = (
            "No Low Volatility window formed a robust neighbouring plateau "
            "under the declared rules."
        )

    lines = [
        "# Low Volatility Deep Dive",
        "",
        "## Scope",
        "",
        f"- Tested lookbacks: `{list(LOW_VOLATILITY_WINDOWS)}` trading days.",
        f"- Fixed anchor: `{LOW_VOLATILITY_ANCHOR_METHOD}`, beta-neutral, rebalance every `{LOW_VOLATILITY_ANCHOR_REBALANCE_DAYS}` days.",
        f"- Primary cost: `{PRIMARY_TRANSACTION_COST_BPS}` bps.",
        "- The complete portfolio grid is retained for description, but every lookback is judged using the same anchor implementation.",
        "- The anchor was discovered after viewing Layer 4, so this is sensitivity research, not a new untouched test.",
        "- Because the factor is negative volatility, Q10 contains the lowest-volatility stocks.",
        "",
        "## Selection-Layer Boundary",
        "",
        "The 63-day Selection result described a lower-tail pattern, while the Layer 4 anchor uses the opposite low-volatility Q10 side. This direction was found post-selection and is therefore labelled explicitly rather than presented as prior confirmation.",
        "",
        markdown_table(
            candidates,
            [
                "factor_key",
                "window",
                "selection_pattern",
                "selection_status",
            ],
            limit=len(candidates),
        ),
        "",
        "## Declared Rules",
        "",
        f"- Net Sharpe at 10 bps >= `{LOW_VOLATILITY_MIN_NET_SHARPE}`.",
        f"- Alpha HAC t-stat at 10 bps >= `{LOW_VOLATILITY_MIN_ALPHA_TSTAT}`.",
        "- The same alpha result must survive Benjamini-Hochberg FDR across all seven anchor windows.",
        "- Positive return at both 10 and 25 bps.",
        "- Every tested calendar phase has positive annualized return.",
        "- The long walk-forward anchor has positive return in every reported market-regime state.",
        f"- Long walk-forward Sharpe >= `{LOW_VOLATILITY_MIN_LONG_WF_SHARPE}` and positive-period rate >= `{LOW_VOLATILITY_MIN_LONG_WF_POSITIVE_RATE:.2f}`.",
        f"- Short walk-forward Sharpe > `{LOW_VOLATILITY_MIN_SHORT_WF_SHARPE}` and positive-period rate >= `{LOW_VOLATILITY_MIN_SHORT_WF_POSITIVE_RATE}`.",
        "- At least one adjacent declared lookback must pass the core economic checks.",
        "",
        "## Window Results",
        "",
        markdown_table(
            summary,
            [
                "window",
                "research_status",
                "net_annualized_return_10bps",
                "net_sharpe_10bps",
                "alpha_hac_tstat_10bps",
                "alpha_bh_q_value_10bps",
                "regression_beta_10bps",
                "net_annualized_return_25bps",
                "maximum_drawdown_10bps",
                "annualized_turnover",
                "long_wf_sharpe",
                "short_wf_sharpe",
                "minimum_regime_annualized_return",
                "neighbour_support_count",
                "passed_declared_checks",
            ],
            limit=len(summary),
        ),
        "",
        "## Benchmarks",
        "",
        markdown_table(
            benchmarks,
            [
                "benchmark",
                "annualized_return",
                "annualized_volatility",
                "sharpe",
                "maximum_drawdown",
            ],
        ),
        "",
        "## Strongest Full-Grid Implementations",
        "",
        "These are descriptive maxima from the searched implementation grid and are not used as independent confirmation.",
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
                "alpha_hac_tstat",
                "annualized_turnover",
                "maximum_drawdown",
            ],
            limit=15,
        ),
        "",
        "## Conclusion",
        "",
        conclusion,
        "",
        "## Limitations",
        "",
        f"- Sector exposure status: `{sector_status.iloc[0]['status']}` — {sector_status.iloc[0]['reason']}",
        "- Candidate and anchor selection used the same historical dataset.",
        "- Yahoo historical availability and residual survivorship bias remain.",
        "- No result from this report is labelled `VALIDATED_ALPHA`.",
        "",
        "## Figures",
        "",
    ]
    for path in figure_paths:
        name = os.path.splitext(os.path.basename(path))[0]
        title = name.replace("_", " ").title()
        lines.extend(
            [
                f"### {title}",
                "",
                f"![{title}](Figures/{os.path.basename(path)})",
                "",
            ]
        )
    return "\n".join(lines)
