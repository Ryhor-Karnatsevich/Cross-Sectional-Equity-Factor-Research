"""Membership-weighted availability of accepted company inputs, not FF model fit."""
from pathlib import Path
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Data/Fama and french/Consolidated"
REPORT = ROOT / "Results/Fama_French/Final_Validation"


def run():
    contract = json.loads((DATA / "acceptance_contract.json").read_text())
    assert contract["accuracy_scope"]
    # Coverage describes the cells actually selected into final matrices. Other
    # accepted vintages are retained for explicit as-of queries, not counted here.
    data = pd.read_parquet(DATA / "selected_observations.parquet")
    member = pd.read_parquet(ROOT / "Data/Data_System/Processed/membership.parquet").astype(bool)
    metrics = ["total_assets", "common_equity", "equity_parent", "revenue", "cost_of_sales", "sga", "interest_expense"]
    rows = []
    annual = data.loc[data.metric.isin(metrics)].copy()
    annual["year"] = annual.date.dt.year
    years = sorted(set(member.index.year - (member.index.month < 7).astype(int)))
    availability = {}
    for year in years:
        known = annual.loc[annual.available_from.le(pd.Timestamp(year, 7, 1))]
        current = known.loc[known.year.eq(year - 1)]
        available = {key: set(values) for key, values in current.groupby("metric").ticker.agg(set).items()}
        for metric in metrics:
            available.setdefault(metric, set())
        # Input coverage only; common equity is not relabelled as FF book equity.
        periods = current.groupby(["ticker", "date"]).metric.agg(set)
        required = {"common_equity", "revenue", "cost_of_sales", "sga", "interest_expense"}
        available["same_period_common_equity_and_all_income_inputs"] = {k[0] for k, v in periods.items() if required.issubset(v)}
        assets = known.loc[known.metric.eq("total_assets"), ["ticker", "date", "year"]].drop_duplicates()
        pairs = assets.loc[assets.year.eq(year - 1)].merge(
            assets.loc[assets.year.eq(year - 2)], on="ticker", suffixes=("", "_previous"))
        pairs = pairs.loc[(pairs.date - pairs.date_previous).dt.days.between(330, 400)]
        available["two_consecutive_annual_assets"] = set(pairs.ticker)
        availability[year] = available
    all_metrics = metrics + ["same_period_common_equity_and_all_income_inputs", "two_consecutive_annual_assets"]
    caps = data.loc[data.metric.eq("market_cap") & data.value.gt(0)].copy()
    caps["month"] = caps.date.dt.to_period("M")
    last_trade = pd.Series(member.index, index=member.index.to_period("M")).groupby(level=0).max()
    last_trade.loc[pd.Period("2007-12")] = pd.Timestamp("2007-12-31")
    caps = caps.loc[caps.date.ge(caps.month.map(last_trade))]
    cap_sets = {key: set(values) for key, values in caps.groupby("month").ticker.agg(set).items()}
    for start in ["2008-01-01", "2010-01-01", "2015-01-01"]:
        period = member.loc[member.index >= start]
        denominator = int(period.values.sum())
        annual_weights = period.groupby(period.index.year - (period.index.month < 7).astype(int)).sum()
        for metric in all_metrics:
            covered = sum(int(weights.loc[weights.index.isin(availability[year][metric])].sum()) for year, weights in annual_weights.iterrows())
            rows.append({"research_start": start, "metric": metric, "covered_member_days": covered,
                         "required_member_days": denominator, "coverage_pct": 100 * covered / denominator})
        monthly = period.groupby(period.index.to_period("M")).sum()
        covered = sum(int(weights.loc[weights.index.isin(cap_sets.get(month - 1, set()))].sum()) for month, weights in monthly.iterrows())
        rows.append({"research_start": start, "metric": "monthly_market_cap_previous_month_end", "covered_member_days": covered,
                     "required_member_days": denominator, "coverage_pct": 100 * covered / denominator})
    table = pd.DataFrame(rows)
    assert table.coverage_pct.between(0, 100).all()
    table.to_csv(DATA / "history_coverage.csv", index=False)
    table.to_csv(REPORT / "history_coverage.csv", index=False)
    view = table.pivot(index="metric", columns="research_start", values="coverage_pct")
    lines = ["# Accepted input coverage", "",
             "Denominator: actual membership ticker-days, not all 900 tickers on all dates.",
             "Annual inputs: preceding-calendar-year fiscal ends, available at July formation. Sources must have passed the final acceptance contract.",
             "Joint input coverage requires one exact fiscal period; no missing expense is filled with zero. This is not certified FF book equity or full model eligibility.",
             "Market cap: observed previous month end; stale repeated dates do not fill months.", "",
             "| Parameter | 2008 onwards | 2010 onwards | 2015 onwards |", "|---|---:|---:|---:|"]
    for metric, row in view.iterrows():
        lines.append(f"| {metric} | {row.iloc[0]:.2f}% | {row.iloc[1]:.2f}% | {row.iloc[2]:.2f}% |")
    (REPORT / "history_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(view.round(3).to_string())


if __name__ == "__main__":
    run()
