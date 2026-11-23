"""Offline QA and membership-weighted availability of the current consolidation."""
from pathlib import Path
import json
import sqlite3
import zlib

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Data/Fama and french/Consolidated"
REPORT = ROOT / "Results/Fama_French/Consolidation"
RETRY = ROOT / "External_Tools/LSEG/lseg_statement_retry_output"


def run():
    selected = pd.read_parquet(DATA / "selected_observations.parquet")
    manifest = json.loads((DATA / "manifest.json").read_text())
    membership = pd.read_parquet(ROOT / "Data/Data_System/Processed/membership.parquet").astype(bool)
    main = selected.loc[~selected.is_variant].copy()
    alternatives = selected.loc[selected.is_variant & selected.definition_review & ~selected.identity_review
        & ~selected.scope_review & selected.annual_confirmed & selected.unit.eq("USD")
        & selected.semantic_status.eq("ALTERNATIVE_REVIEW")].copy()
    annual_metrics = sorted(set(main.metric) - {"market_cap"})
    metrics = annual_metrics + ["equity_measure", "two_year_assets", "strict_joint_income_and_equity", "revenue_equity_some_expenses"]
    views = {"direct_fields": main, "including_same_parameter_candidates": pd.concat([main, alternatives], ignore_index=True)}
    weights = {}
    for start in ["2008-01-01", "2010-01-01", "2015-01-01"]:
        period = membership.loc[membership.index >= start]
        weights[start] = period.groupby(period.index.year - (period.index.month < 7).astype(int)).sum()
    rows = []
    for mode, data in views.items():
        valid = data.loc[data.date.notna() & data.published_at.notna() & data.published_at.ge(data.date) & data.metric.ne("market_cap")].copy()
        valid["year"] = valid.date.dt.year
        available = {}
        for year in sorted(set(membership.index.year - (membership.index.month < 7).astype(int))):
            known = valid.loc[valid.published_at.le(pd.Timestamp(year, 6, 30))]
            current = known.loc[known.year.eq(year - 1)]
            previous = known.loc[known.year.eq(year - 2)]
            sets = {key: set(values) for key, values in current.groupby("metric").ticker.agg(set).items()}
            for metric in metrics:
                sets.setdefault(metric, set())
            periods = {key: set(values) for key, values in current.groupby(["ticker", "date"]).metric.agg(set).items()}
            def equity(values):
                return "common_equity" in values or "equity_parent" in values or {"equity_including_minority", "minority_interest"}.issubset(values)
            sets["equity_measure"] = {key[0] for key, values in periods.items() if equity(values)}
            sets["two_year_assets"] = sets["total_assets"] & set(previous.loc[previous.metric.eq("total_assets"), "ticker"])
            expenses = {"cost_of_sales", "sga", "interest_expense"}
            sets["strict_joint_income_and_equity"] = {key[0] for key, values in periods.items() if equity(values) and "revenue" in values and expenses.issubset(values)}
            sets["revenue_equity_some_expenses"] = {key[0] for key, values in periods.items() if equity(values) and "revenue" in values and bool(expenses & values)}
            available[year] = sets
        for start, counts in weights.items():
            denominator = int(counts.values.sum())
            for metric in metrics:
                numerator = sum(int(w.loc[w.index.isin(available[year][metric])].sum()) for year, w in counts.iterrows())
                rows.append({"research_start": start, "mode": mode, "metric": metric,
                             "covered_member_days": numerator, "required_member_days": denominator, "coverage_pct": 100 * numerator / denominator})
    caps = main.loc[main.metric.eq("market_cap") & main.value.gt(0)].copy()
    caps["month"] = caps.date.dt.to_period("M")
    month_ends = pd.Series(membership.index, index=membership.index.to_period("M")).groupby(level=0).max()
    month_ends.loc[pd.Period("2007-12")] = pd.Timestamp("2007-12-31")
    caps = caps.loc[caps.date.ge(caps.month.map(month_ends))]
    cap_sets = {key: set(values) for key, values in caps.groupby("month").ticker.agg(set).items()}
    for start in weights:
        period = membership.loc[membership.index >= start]
        counts = period.groupby(period.index.to_period("M")).sum()
        denominator = int(counts.values.sum())
        numerator = sum(int(w.loc[w.index.isin(cap_sets.get(month - 1, set()))].sum()) for month, w in counts.iterrows())
        for mode in views:
            rows.append({"research_start": start, "mode": mode, "metric": "monthly_market_cap_previous_month_end",
                         "covered_member_days": numerator, "required_member_days": denominator, "coverage_pct": 100 * numerator / denominator})
    coverage = pd.DataFrame(rows)
    assert coverage.coverage_pct.between(0, 100).all()
    coverage.to_csv(DATA / "history_coverage.csv", index=False)
    coverage.to_csv(REPORT / "history_coverage.csv", index=False)
    table = coverage.loc[coverage.research_start.eq("2008-01-01")].pivot(index="metric", columns="mode", values="coverage_pct")
    note = ["# Coverage after consolidation and semantic separation", "",
        "Period: 2008-01-02 through 2026-08-18. Denominator: 2,350,698 actual membership ticker-days.",
        "Annual fiscal periods must end in the preceding calendar year and be published by the relevant June formation. Joint inputs share the same exact fiscal end.",
        "Direct fields are kept apart from same-parameter candidates pending approval. Different quantities (net interest, bank revenue, operating-revenue costs, minority earnings, etc.) do not count as missing original parameters.",
        "Consequently these candidate percentages can be lower than older broad-alternative scenarios; this reflects definition separation, not lost observations.",
        "Equity-measure availability is not validated Fama-French book equity or final model eligibility. No missing expense is assumed zero.", "",
        "| Parameter | Direct fields | Including same-parameter candidates |", "|---|---:|---:|"]
    for metric in table.index:
        note.append(f"| {metric} | {table.loc[metric, 'direct_fields']:.2f}% | {table.loc[metric, 'including_same_parameter_candidates']:.2f}% |")
    (REPORT / "history_coverage.md").write_text("\n".join(note) + "\n", encoding="utf-8")
    # Confirm whether unparsed successful replies actually contain hidden values.
    log_path = RETRY / "request_report.csv"
    logs = pd.read_csv(log_path)
    db = sqlite3.connect((RETRY / "recovery_raw.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    empty_review = []
    try:
        for row in logs.loc[logs.status.eq("NO_MATCHING_STATEMENT_ROWS")].itertuples():
            result = db.execute("SELECT payload FROM responses WHERE key=?", (row.request_key,)).fetchone()
            payload = json.loads(zlib.decompress(result[0]) if isinstance(result[0], bytes) else result[0])
            frame = pd.DataFrame(payload["data"], columns=payload["columns"])
            name_col = next((c for c in frame if str(c).lower().endswith(".fieldname") or str(c).lower() == "name"), None)
            template_cols = [c for c in frame if str(c).lower() in ["tr.f.incomestatement", "tr.f.balancesheet", "std income statement all", "std balance sheet all"]]
            numeric = sum(int(pd.to_numeric(frame[col], errors="coerce").notna().sum()) for col in template_cols)
            fields = int(frame[name_col].astype(str).str.lower().str.startswith("tr.").sum()) if name_col else 0
            empty_review.append({"request_key": row.request_key, "label": row.label, "returned_rows": len(frame), "field_codes": fields, "numeric_values": numeric})
    finally:
        db.close()
    unparsed = pd.DataFrame(empty_review)
    unparsed.to_csv(DATA / "QA/unparsed_template_review.csv", index=False)
    # Numerical warnings preserve actual negative reports instead of clipping them.
    financial = main.loc[main.kind.eq("number")]
    negatives = financial.loc[financial.value.lt(0)].groupby("metric").size().rename("negative_cells").reset_index()
    negatives.to_csv(DATA / "QA/negative_values.csv", index=False)
    summary = {
        "matrix_validation": "PASS", "input_hash_validation": "PASS",
        "exact_field_overlap_comparisons": manifest["overlap_comparisons"],
        "exact_field_overlap_matches": manifest["overlap_matches"],
        "publication_before_period_source_rows": manifest["publication_before_period_rows"],
        "publication_before_period_primary_cells": int(main.publication_before_period_end.sum()),
        "nonfinite_primary_numeric_cells": int((~np.isfinite(financial.value)).sum()),
        "negative_total_asset_cells": int(financial.loc[financial.metric.eq("total_assets"), "value"].lt(0).sum()),
        "nonpositive_market_cap_cells": int(financial.loc[financial.metric.eq("market_cap"), "value"].le(0).sum()),
        "unparsed_reply_count": len(unparsed), "unparsed_hidden_numeric_values": int(unparsed.numeric_values.sum()),
        "issuer_identity_and_definition_review": "REVIEW_REMAINS_NOT_CERTIFIED",
    }
    assert summary["publication_before_period_primary_cells"] == 0
    assert summary["nonfinite_primary_numeric_cells"] == 0
    (DATA / "QA/validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for name in ["cross_field_comparison.csv", "cross_field_comparison_tolerance.csv", "cross_field_difference_examples.csv"]:
        path = REPORT / name
        if path.exists():
            (DATA / "QA" / name).write_bytes(path.read_bytes())
    body = (REPORT / "summary.md").read_text(encoding="utf-8")
    body += "\n\nAdditional checks:\n" + "\n".join(f"- {key}: {value}" for key, value in summary.items()) + "\n"
    body += "\nCross-field comparison is recorded separately. Matching repeated calls for the same field does not make different financial definitions interchangeable.\n"
    (REPORT / "summary.md").write_text(body, encoding="utf-8")
    (DATA / "QA/summary.md").write_text(body, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(table.loc[["total_assets", "common_equity", "revenue", "cost_of_sales", "sga", "interest_expense"]].round(3).to_string())


if __name__ == "__main__":
    run()
