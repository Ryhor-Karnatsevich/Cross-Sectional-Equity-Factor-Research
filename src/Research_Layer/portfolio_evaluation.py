import numpy as np
import pandas as pd
import statsmodels.api as sm

from research_config import (
    ANNUALIZATION_FACTOR,
    ECONOMIC_LEAD_MIN_LONG_WF_POSITIVE_RATE,
    ECONOMIC_LEAD_MIN_LONG_WF_SHARPE,
    ECONOMIC_LEAD_MIN_NET_SHARPE,
    MARKET_NEUTRAL_METHODS,
    PRIMARY_TRANSACTION_COST_BPS,
    REGRESSION_HAC_LAGS,
    RESEARCH_START_DATE,
    TRANSACTION_COST_BPS,
)


def apply_transaction_costs(gross_returns, turnover, cost_bps):
    costs = turnover * float(cost_bps) / 10_000
    return (1 + gross_returns) * (1 - costs) - 1


def annualized_return(returns):
    returns = pd.Series(returns).dropna()
    if returns.empty:
        return np.nan
    wealth = (1 + returns).prod()
    if not np.isfinite(wealth) or wealth <= 0:
        return np.nan
    return float(wealth ** (ANNUALIZATION_FACTOR / len(returns)) - 1)


def annualized_sharpe(excess_returns):
    excess_returns = pd.Series(excess_returns).dropna()
    if len(excess_returns) < 2 or excess_returns.std() <= 0:
        return np.nan
    return float(
        excess_returns.mean()
        / excess_returns.std()
        * np.sqrt(ANNUALIZATION_FACTOR)
    )


def maximum_drawdown(returns):
    returns = pd.Series(returns).dropna()
    if returns.empty:
        return np.nan
    wealth = (1 + returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1
    return float(drawdown.min())


def direction_rate(returns, frequency):
    returns = pd.Series(returns).dropna()
    if returns.empty:
        return np.nan
    compounded = (1 + returns).groupby(returns.index.to_period(frequency)).prod() - 1
    return float((compounded > 0).mean()) if len(compounded) else np.nan


def alpha_beta_test(returns, market_return, risk_free, portfolio_type):
    if portfolio_type == "long_only":
        dependent = returns - risk_free
        independent = market_return - risk_free
    else:
        dependent = returns
        independent = market_return

    data = pd.concat(
        [dependent.rename("portfolio"), independent.rename("market")],
        axis=1,
    ).dropna()
    if len(data) < 60 or data["market"].var() <= 0:
        return np.nan, np.nan, np.nan, np.nan

    model = sm.OLS(
        data["portfolio"],
        sm.add_constant(data["market"]),
    ).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": REGRESSION_HAC_LAGS},
    )
    return (
        float(model.params["const"] * ANNUALIZATION_FACTOR),
        float(model.tvalues["const"]),
        float(model.pvalues["const"]),
        float(model.params["market"]),
    )


def evaluate_one_path(
    gross_returns,
    turnover,
    beta_exposure,
    gross_exposure,
    net_exposure,
    unpriced_weight,
    max_sector_exposure,
    unknown_sector_weight,
    max_position,
    holding_count,
    market_return,
    risk_free,
    portfolio_type,
    cost_bps,
):
    active = gross_exposure > 0
    if not active.any():
        return {"observations": 0}
    start = active[active].index[0]
    gross_returns = gross_returns.loc[start:]
    turnover = turnover.loc[start:]
    beta_exposure = beta_exposure.loc[start:]
    gross_exposure = gross_exposure.loc[start:]
    net_exposure = net_exposure.loc[start:]
    unpriced_weight = unpriced_weight.loc[start:]
    max_sector_exposure = max_sector_exposure.loc[start:]
    unknown_sector_weight = unknown_sector_weight.loc[start:]
    max_position = max_position.loc[start:]
    holding_count = holding_count.loc[start:]
    market_return = market_return.loc[start:]
    risk_free = risk_free.loc[start:]

    net_returns = apply_transaction_costs(
        gross_returns,
        turnover,
        cost_bps,
    )
    excess = (
        net_returns - risk_free
        if portfolio_type == "long_only"
        else net_returns
    )
    alpha, alpha_tstat, alpha_p_value, regression_beta = alpha_beta_test(
        net_returns,
        market_return,
        risk_free,
        portfolio_type,
    )

    return {
        "observations": int(net_returns.notna().sum()),
        "annualized_return": annualized_return(net_returns),
        "annualized_volatility": float(
            net_returns.std() * np.sqrt(ANNUALIZATION_FACTOR)
        ),
        "sharpe": annualized_sharpe(excess),
        "maximum_drawdown": maximum_drawdown(net_returns),
        "positive_month_rate": direction_rate(net_returns, "M"),
        "positive_year_rate": direction_rate(net_returns, "Y"),
        "annualized_alpha": alpha,
        "alpha_hac_tstat": alpha_tstat,
        "alpha_raw_p_value": alpha_p_value,
        "regression_beta": regression_beta,
        "average_estimated_beta": float(beta_exposure.mean()),
        "maximum_absolute_estimated_beta": float(beta_exposure.abs().max()),
        "average_gross_exposure": float(gross_exposure.mean()),
        "average_net_exposure": float(net_exposure.mean()),
        "annualized_turnover": float(
            turnover.mean() * ANNUALIZATION_FACTOR
        ),
        "annualized_cost_drag": float(
            turnover.mean()
            * ANNUALIZATION_FACTOR
            * float(cost_bps)
            / 10_000
        ),
        "unpriced_weight_days": int((unpriced_weight > 0).sum()),
        "maximum_unpriced_weight": float(unpriced_weight.max()),
        "average_maximum_sector_exposure": (
            float(max_sector_exposure.mean())
            if max_sector_exposure.ne(0).any()
            else np.nan
        ),
        "maximum_sector_exposure": (
            float(max_sector_exposure.max())
            if max_sector_exposure.ne(0).any()
            else np.nan
        ),
        "average_unknown_sector_weight": (
            float(unknown_sector_weight.mean())
            if max_sector_exposure.ne(0).any()
            else np.nan
        ),
        "average_holding_count": float(holding_count.mean()),
        "minimum_holding_count": float(holding_count.min()),
        "maximum_position_weight": float(max_position.max()),
    }


def evaluate_portfolios(matrices, metadata, market_return, risk_free):
    rows = []
    metadata_lookup = metadata.set_index("path_key")
    if not metadata_lookup.index.is_unique:
        raise ValueError("Duplicated portfolio path metadata")
    for number, path in enumerate(matrices["gross_returns"].columns, start=1):
        if number == 1 or number % 25 == 0:
            print(f"Portfolio statistics {number}/{len(metadata_lookup)}")
        identity = metadata_lookup.loc[path].to_dict()
        for cost_bps in TRANSACTION_COST_BPS:
            metrics = evaluate_one_path(
                matrices["gross_returns"][path],
                matrices["turnover"][path],
                matrices["beta_exposure"][path],
                matrices["gross_exposure"][path],
                matrices["net_exposure"][path],
                matrices["unpriced_weight"][path],
                matrices["max_sector_exposure"][path],
                matrices["unknown_sector_weight"][path],
                matrices["max_position"][path],
                matrices["holding_count"][path],
                market_return,
                risk_free,
                identity["portfolio_type"],
                cost_bps,
            )
            rows.append(
                {
                    "path_key": path,
                    **identity,
                    "transaction_cost_bps": cost_bps,
                    "sharpe_basis": (
                        "return_minus_risk_free"
                        if identity["portfolio_type"] == "long_only"
                        else "self_financing_spread_return"
                    ),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def benchmark_statistics(market_return, risk_free):
    data = pd.concat(
        [
            market_return.rename("equal_weight_market"),
            risk_free.rename("risk_free"),
        ],
        axis=1,
    ).loc[RESEARCH_START_DATE:]
    rows = []
    for name in data.columns:
        values = data[name].dropna()
        excess = (
            values - data["risk_free"].reindex(values.index)
            if name == "equal_weight_market"
            else values * 0.0
        )
        rows.append(
            {
                "benchmark": name,
                "observations": len(values),
                "annualized_return": annualized_return(values),
                "annualized_volatility": float(
                    values.std() * np.sqrt(ANNUALIZATION_FACTOR)
                ),
                "sharpe": annualized_sharpe(excess),
                "maximum_drawdown": maximum_drawdown(values),
            }
        )
    return pd.DataFrame(rows)


def candidate_decisions(candidates, statistics, walk_forward_summary):
    primary = statistics.loc[
        statistics["transaction_cost_bps"].eq(
            PRIMARY_TRANSACTION_COST_BPS
        )
        & statistics["portfolio_type"].eq("market_neutral")
    ]
    rows = []

    for candidate in candidates.itertuples(index=False):
        factor_stats = primary.loc[
            primary["factor_key"].eq(candidate.factor_key)
        ].sort_values("sharpe", ascending=False)
        factor_walk = walk_forward_summary.loc[
            walk_forward_summary["factor_key"].eq(candidate.factor_key)
            & walk_forward_summary["portfolio_type"].eq("market_neutral")
        ]

        best = factor_stats.iloc[0] if not factor_stats.empty else None
        selected_walk = (
            factor_walk.loc[factor_walk["path_key"].eq(best["path_key"])]
            if best is not None
            else factor_walk.iloc[0:0]
        )
        long_walk = selected_walk.loc[
            selected_walk["walk_forward_scheme"].eq("long")
        ]
        short_walk = selected_walk.loc[
            selected_walk["walk_forward_scheme"].eq("short")
        ]
        best_long = long_walk.iloc[0] if len(long_walk) == 1 else None
        best_short = short_walk.iloc[0] if len(short_walk) == 1 else None
        economic_lead = bool(
            best is not None
            and best_long is not None
            and best["annualized_return"] > 0
            and best["sharpe"] >= ECONOMIC_LEAD_MIN_NET_SHARPE
            and best_long["stitched_oos_sharpe"]
            >= ECONOMIC_LEAD_MIN_LONG_WF_SHARPE
            and best_long["positive_oos_period_rate"]
            >= ECONOMIC_LEAD_MIN_LONG_WF_POSITIVE_RATE
        )
        statistical_lead = "global_fdr" in str(
            candidate.selection_evidence
        )

        if economic_lead:
            status = "ECONOMIC_LEAD"
            reason = (
                "Positive net market-neutral implementation and coherent "
                "long walk-forward behaviour."
            )
        elif statistical_lead:
            status = "STATISTICAL_LEAD"
            reason = (
                "Rank signal survived global FDR but did not meet the "
                "economic implementation rule."
            )
        else:
            status = "REJECTED"
            reason = "Did not meet the declared statistical or economic rule."

        rows.append(
            {
                "factor_key": candidate.factor_key,
                "final_status": status,
                "validated_alpha": False,
                "best_method": best["method"] if best is not None else None,
                "best_beta_neutral": (
                    best["beta_neutral"] if best is not None else None
                ),
                "best_rebalance_days": (
                    best["rebalance_days"] if best is not None else None
                ),
                "evaluated_path_key": (
                    best["path_key"] if best is not None else None
                ),
                "best_net_annualized_return": (
                    best["annualized_return"] if best is not None else np.nan
                ),
                "best_net_sharpe": (
                    best["sharpe"] if best is not None else np.nan
                ),
                "best_alpha_hac_tstat": (
                    best["alpha_hac_tstat"] if best is not None else np.nan
                ),
                "best_long_wf_sharpe": (
                    best_long["stitched_oos_sharpe"]
                    if best_long is not None
                    else np.nan
                ),
                "best_long_wf_positive_rate": (
                    best_long["positive_oos_period_rate"]
                    if best_long is not None
                    else np.nan
                ),
                "best_short_wf_sharpe": (
                    best_short["stitched_oos_sharpe"]
                    if best_short is not None
                    else np.nan
                ),
                "decision_reason": reason,
                "validation_limit": (
                    "Post-selection history; no untouched final sample."
                ),
            }
        )
    return pd.DataFrame(rows)
