"""Refine the existing SEC downloads offline; preserve first-pass outputs."""

import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Fama_French.config import CONCEPTS, FLOW_METRICS, OUTPUT_DIR, PROJECT_ROOT
from Fama_French.sec_edgar import build_annual_table, extract_annual_facts, save_frame, write_json


SUPPLEMENTAL_CONCEPTS = {
    "gross_profit": {"us-gaap": ("GrossProfit",), "ifrs-full": ("GrossProfit",)},
    "selling_marketing": {"us-gaap": ("SellingAndMarketingExpense",)},
    "selling_only": {"us-gaap": ("SellingExpense",)},
    "general_administrative": {"us-gaap": ("GeneralAndAdministrativeExpense",)},
    "revenue_goods": {"us-gaap": ("SalesRevenueGoodsNet",)},
    "revenue_services": {"us-gaap": ("SalesRevenueServicesNet",)},
    # Retained for review, not silently substituted for differently scoped totals.
    "cost_of_services_component": {"us-gaap": ("CostOfServices",)},
    "cost_of_sales_excluding_da": {"us-gaap": (
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    )},
    "interest_debt_component": {"us-gaap": ("InterestExpenseDebt",)},
}
PERIOD_KEYS = ["cik", "period_start", "period_end", "filed", "form", "accession", "unit"]


def agreed_source(group, metric):
    available = group.loc[group.metric.eq(metric)].sort_values("concept_priority")
    values = available.value.to_numpy(dtype=float)
    if not len(values) or not np.isfinite(values).all():
        return None
    if not np.allclose(values, values[0], rtol=1e-9, atol=0.01):
        return None
    return available.iloc[0]


def recover_accounting_identities(frame):
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["recovery_rule"] = "reported_source"
    frame["source_components"] = frame.taxonomy + ":" + frame.concept
    frame["scope_review_required"] = False
    recovered = []
    flows = frame.loc[frame.duration_days.between(300, 400)]
    for _, group in flows.groupby(PERIOD_KEYS, dropna=False, sort=False):
        present = set(group.metric)
        recipes = []
        if "revenue" not in present:
            recipes.append(("revenue", "goods_plus_services_revenue", "revenue_goods", "revenue_services", 1))
        if "sga" not in present:
            selling = "selling_marketing" if "selling_marketing" in present else "selling_only"
            recipes.append(("sga", "selling_plus_general_administrative", selling, "general_administrative", 1))
        if "cost_of_sales" not in present:
            recipes.append(("cost_of_sales", "revenue_minus_gross_profit", "revenue", "gross_profit", -1))
        for metric, rule, left_metric, right_metric, sign in recipes:
            left, right = agreed_source(group, left_metric), agreed_source(group, right_metric)
            if left is None or right is None:
                continue
            value = float(left.value) + sign * float(right.value)
            if value < 0:  # An invalid identity is not repaired by clipping.
                continue
            row = left.to_dict()
            row.update(metric=metric, value=value, taxonomy="derived_accounting_identity",
                       concept=rule, concept_priority=100, recovery_rule=rule,
                       source_components=f"{left.taxonomy}:{left.concept} {'+' if sign == 1 else '-'} {right.taxonomy}:{right.concept}")
            if metric == "cost_of_sales" and left.concept not in {"Revenues", "SalesRevenueNet", "Revenue"}:
                # Contract revenue can exclude other revenue streams, or include
                # assessed taxes. Its scope need not match reported gross profit.
                row["metric"] = "cost_of_sales_scope_review"
                row["scope_review_required"] = True
            recovered.append(row)
    if recovered:
        frame = pd.concat([frame, pd.DataFrame(recovered)], ignore_index=True)
    return frame


def required_period_coverage(annual, mapping, membership, stage):
    links = mapping.loc[mapping.mapping_status.eq("SINGLE_CIK_CANDIDATE")].set_index("ticker").cik
    data = annual.loc[annual.unit.eq("USD")].copy()
    fields = ["total_assets", "equity_parent", "common_equity", "equity_including_minority",
              "minority_interest", "revenue", "cost_of_sales", "sga", "interest_expense"]
    for field in fields:
        if field not in data:
            data[field] = np.nan
        conflicts = data.conflicting_metrics.fillna("").str.split("|", regex=False).map(lambda names: field in names)
        data.loc[conflicts, field] = np.nan
    formation = membership.index.year - (membership.index.month < 7).astype(int)
    availability = {}
    basic = ["total_assets", "revenue", "cost_of_sales", "sga", "interest_expense"]
    for year in sorted(set(formation)):
        known = data.loc[data.filed.le(pd.Timestamp(year, 6, 30))]
        current = known.loc[known.period_year.eq(year - 1)]
        previous = known.loc[known.period_year.eq(year - 2)]
        ciks = {metric: set(current.loc[current[metric].notna(), "cik"]) for metric in basic}
        equity = current.equity_parent.notna() | current.common_equity.notna() | (current.equity_including_minority.notna() & current.minority_interest.notna())
        ciks["equity_measure"] = set(current.loc[equity, "cik"])
        ciks["two_year_assets"] = ciks["total_assets"] & set(previous.loc[previous.total_assets.notna(), "cik"])
        all_expenses = current[["cost_of_sales", "sga", "interest_expense"]].notna().all(axis=1)
        some_expenses = current[["cost_of_sales", "sga", "interest_expense"]].notna().any(axis=1)
        ciks["strict_joint_income_and_equity"] = set(current.loc[equity & current.revenue.notna() & all_expenses, "cik"])
        ciks["revenue_equity_some_expenses"] = set(current.loc[equity & current.revenue.notna() & some_expenses, "cik"])
        availability[year] = {metric: set(links.loc[links.isin(values)].index) for metric, values in ciks.items()}
    rows = []
    for start in ("2008-01-01", "2010-01-01", "2015-01-01"):
        period = membership.loc[membership.index >= start]
        counts = period.groupby(period.index.year - (period.index.month < 7).astype(int)).sum()
        denominator = int(period.to_numpy().sum())
        for metric in basic + ["equity_measure", "two_year_assets", "strict_joint_income_and_equity", "revenue_equity_some_expenses"]:
            numerator = sum(int(weights.loc[weights.index.isin(availability[year][metric])].sum()) for year, weights in counts.iterrows())
            rows.append({"stage": stage, "research_start": start, "metric": metric,
                         "covered_member_days": numerator, "required_member_days": denominator,
                         "coverage_pct": 100 * numerator / denominator})
    return pd.DataFrame(rows)


def run():
    root = OUTPUT_DIR / "Refined"
    root.mkdir(parents=True, exist_ok=True)
    original = OUTPUT_DIR / "Processed/annual_fundamentals_by_filing.parquet"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    baseline = pd.read_parquet(original)
    concepts = copy.deepcopy(CONCEPTS)
    concepts.update(SUPPLEMENTAL_CONCEPTS)
    flows = FLOW_METRICS | set(SUPPLEMENTAL_CONCEPTS)
    frames = []
    files = sorted((OUTPUT_DIR / "Raw/CompanyFacts").glob("*.gz"))
    print(f"Offline refinement: {len(files)} cached issuers; no network downloads", flush=True)
    for number, path in enumerate(files, 1):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            data = json.load(stream)
        frame = extract_annual_facts(data, concepts=concepts, flow_metrics=flows)
        if len(frame):
            frames.append(recover_accounting_identities(frame))
        if number % 100 == 0:
            print(f"Processed cached issuer {number}/{len(files)}", flush=True)
    facts = pd.concat(frames, ignore_index=True)
    annual = build_annual_table(facts)
    recovered = facts.loc[facts.recovery_rule.ne("reported_source")].copy()
    save_frame(facts, root / "annual_facts_all_versions.parquet")
    save_frame(annual, root / "annual_fundamentals_by_filing.parquet")
    save_frame(recovered, root / "recovered_observations.parquet")
    mapping = pd.read_csv(OUTPUT_DIR / "ticker_cik_mapping.csv", dtype={"cik": str}, keep_default_na=False)
    membership = pd.read_parquet(PROJECT_ROOT / "Data/Data_System/Processed/membership.parquet").astype(bool)
    coverage = pd.concat([
        required_period_coverage(baseline, mapping, membership, "first_pass"),
        required_period_coverage(annual, mapping, membership, "refined"),
    ], ignore_index=True)
    save_frame(coverage, root / "coverage_by_required_period.csv")
    assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
    summary = {"cached_issuers_read": len(files), "http_requests": 0,
               "source_observations": len(facts), "annual_filing_rows": len(annual),
               "recovered_observations": len(recovered),
               "recovered_observations_without_scope_flag": int((~recovered.scope_review_required).sum()),
               "scope_review_observations": int(recovered.scope_review_required.sum()),
               "recovery_rules": recovered.recovery_rule.value_counts().to_dict(),
               "original_processed_dataset_unchanged": True,
               "mapping_verified": False, "complete_fama_french_inputs": False}
    write_json(root / "run_metadata.json", summary)
    selected = coverage.loc[coverage.research_start.eq("2010-01-01")].pivot(index="metric", columns="stage", values="coverage_pct")
    lines = ["# SEC Offline Refinement", "", "Original raw downloads and first-pass processed files are unchanged.",
             "", f"Recovered **{int((~recovered.scope_review_required).sum()):,}** annual source observations using matched accounting identities; **zero** new HTTP requests. Another **{int(recovered.scope_review_required.sum()):,}** observations are separate scope-review candidates and do not fill the primary input fields.",
             "", "## Coverage for 2010–2026", "", "| Input | First pass | Refined |", "| --- | ---: | ---: |"]
    for metric, row in selected.iterrows():
        lines.append(f"| {metric} | {row.first_pass:.2f}% | {row.refined:.2f}% |")
    lines += ["", "Coverage is weighted by actual index-membership dates. Only single-CIK candidates, USD values, no flagged concept conflicts and statements filed by the preceding June formation are counted. These are input-availability measures, not verified FF5 eligibility.",
              "", "## Recovery rules", "", "- SG&A = selling/marketing expense + general/administrative expense, or selling expense + general/administrative expense.",
              "- Cost of sales = revenue minus gross profit, only where no original cost-of-sales concept exists and the revenue concept is a broad reported total. Contract-revenue candidates remain separate pending scope reconciliation.",
              "- Revenue = goods revenue + service revenue, only where no original revenue concept exists.",
              "- Every component must match issuer, annual start/end dates, filing accession/date, form and currency. Conflicting component values and negative derived costs are rejected.",
              "- Narrower cost and debt-interest concepts are extracted separately for review; they are not silently substituted for totals. Missing values are not filled with zero.",
              "", "Book-equity definitions, expense applicability, historical identity intervals and market capitalization still require preparation. No portfolio or statistical model is run.", ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(selected.round(2).to_string(), flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    run()
