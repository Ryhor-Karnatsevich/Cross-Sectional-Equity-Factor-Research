"""Offline integration/QA of all downloaded SEC and LSEG company data.

Builds a fresh staging directory. Publishing replaces no source download and
archives the prior consolidated directory. Exact field-code mapping only.
"""
from pathlib import Path
import importlib.util
import json
import shutil
import time
import uuid

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("previous_consolidation", Path(__file__).with_name("consolidate_ff_downloads.py"))
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)
BASE = ROOT / "Data/Fama and french"
ORIGINAL = ROOT / "External_Tools/LSEG/lseg_company_data_output"
RECOVERY = ROOT / "LSEG_Recovery/lseg_company_recovery_output"
COMPLETION = ROOT / "External_Tools/LSEG/lseg_company_completion_output"
RETRY = ROOT / "External_Tools/LSEG/lseg_statement_retry_output"
TARGET = BASE / "Consolidated"
REPORT = ROOT / "Results/Fama_French/Consolidation"

# metric, unit, semantic classification. Alternatives are never filled into
# main parameters automatically. Different quantities receive different names.
FIELD_RULES = {
    "tr.totalassetsreported": ("total_assets", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.totalrevenue": ("revenue", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.costofrevenuetotal": ("cost_of_sales", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.sgaexpensetotal": ("sga", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.interestexpense": ("interest_expense", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.f.shholdeqcom": ("common_equity", "USD", "DIRECT_EXISTING_FIELD"),
    "tr.totalequity": ("total_equity_lseg_provider", "USD", "DISTINCT_SCOPE"),
    "tr.f.totassets": ("total_assets", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.totrevenue": ("revenue", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.totrevbizactiv": ("revenue", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.cogstot": ("cost_of_sales", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.sgatot": ("sga", "USD", "ALTERNATIVE_REVIEW"),
    "tr.banktotalrevenue": ("bank_total_revenue", "USD", "DISTINCT_SCOPE"),
    "tr.f.costofoprev": ("cost_of_operating_revenue", "USD", "DISTINCT_SCOPE"),
    "tr.f.intrexpn": ("net_interest_expense_lseg", "USD", "DISTINCT_SCOPE"),
    "tr.f.minintr": ("minority_earnings", "USD", "DISTINCT_SCOPE"),
    "tr.f.minintreq": ("minority_interest", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.shholdeqparentshholdtot": ("equity_parent", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.comeqtot": ("common_equity_total_lseg", "USD", "DISTINCT_SCOPE"),
    "tr.f.totshholdeq": ("equity_including_minority_and_hybrid", "USD", "DISTINCT_SCOPE"),
    "tr.f.prefshholdeq": ("preferred_equity", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.bvexclothEq".lower(): ("book_value_excluding_other_equity", "USD", "DISTINCT_SCOPE"),
    "tr.f.tangbv": ("tangible_book_value", "USD", "DISTINCT_SCOPE"),
    "tr.f.totbookcap": ("total_book_capital", "USD", "DISTINCT_SCOPE"),
    "tr.f.grossprofindproptot": ("gross_profit", "USD", "ALTERNATIVE_REVIEW"),
    "tr.f.revgoodssrvc": ("revenue_goods_and_services", "USD", "COMPONENT_NOT_TOTAL"),
    "tr.f.sgaexclrnd": ("sga_excluding_rnd", "USD", "COMPONENT_NOT_TOTAL"),
    "tr.f.sgaunclassif": ("sga_unclassified_component", "USD", "COMPONENT_NOT_TOTAL"),
    "tr.f.sgaothtot": ("sga_other_component", "USD", "COMPONENT_NOT_TOTAL"),
    "tr.f.cogsexcldepr": ("cost_of_sales_excluding_da", "USD", "COMPONENT_NOT_TOTAL"),
    "tr.f.cogsinclopmaintutiltot": ("costs_including_utility_operations", "USD", "DISTINCT_SCOPE"),
    "tr.f.intrexpnnetofintrinc": ("interest_expense_net_of_interest_income", "USD", "DISTINCT_SCOPE"),
    "tr.f.intrexpnnetofcapintr": ("interest_expense_net_of_capitalized_interest", "USD", "DISTINCT_SCOPE"),
    "tr.f.intrexpnfinTot".lower(): ("interest_expense_finance_total", "USD", "DISTINCT_SCOPE"),
    "tr.f.intrexpnOnCapFinGross".lower(): ("interest_expense_capital_financing_gross", "USD", "DISTINCT_SCOPE"),
    "tr.f.nonintrexpnbank": ("bank_non_interest_expense", "USD", "DISTINCT_SCOPE"),
    "tr.f.opexpntot": ("total_operating_expenses", "USD", "DISTINCT_SCOPE"),
    "tr.f.ebit": ("ebit", "USD", "DISTINCT_SCOPE"),
    "tr.f.incbefTax".lower(): ("income_before_tax", "USD", "DISTINCT_SCOPE"),
    "tr.f.opprofbefnonrecurincexpn": ("operating_profit_before_nonrecurring_items", "USD", "DISTINCT_SCOPE"),
    "tr.bsoriginalannouncementdate": ("balance_announcement", "date", "DIRECT_EXISTING_FIELD"),
    "tr.isoriginalannouncementdate": ("income_announcement", "date", "DIRECT_EXISTING_FIELD"),
    "tr.companymarketcap": ("market_cap", "USD", "DIRECT_EXISTING_FIELD"),
}
FLOW_METRICS = {"revenue", "cost_of_sales", "sga", "interest_expense", "gross_profit", "bank_total_revenue",
                "cost_of_operating_revenue", "net_interest_expense_lseg", "minority_earnings", "income_announcement",
                "revenue_goods_and_services", "sga_excluding_rnd", "sga_unclassified_component", "sga_other_component",
                "cost_of_sales_excluding_da", "costs_including_utility_operations", "interest_expense_net_of_interest_income",
                "interest_expense_net_of_capitalized_interest", "interest_expense_finance_total",
                "interest_expense_capital_financing_gross", "bank_non_interest_expense", "total_operating_expenses",
                "ebit", "income_before_tax", "operating_profit_before_nonrecurring_items"}
FLOW_CODES = {code for code, rule in FIELD_RULES.items() if rule[0] in FLOW_METRICS}
BALANCE_ANCHORS = {"tr.totalassetsreported", "tr.f.totassets", "tr.f.shholdeqcom", "tr.totalequity", "tr.bsoriginalannouncementdate"}


def apply_field_rules(frame, identity=False):
    out = frame.copy()
    code = out.field.str.lower()
    known = code.isin(FIELD_RULES)
    out["semantic_status"] = code.map({k: v[2] for k, v in FIELD_RULES.items()}).fillna("UNASSIGNED_PROVIDER_FIELD")
    out.loc[known, "metric"] = code.loc[known].map({k: v[0] for k, v in FIELD_RULES.items()})
    out.loc[known, "unit"] = code.loc[known].map({k: v[1] for k, v in FIELD_RULES.items()})
    out.loc[~known, "metric"] = "unassigned__" + code.loc[~known].map(previous.slug)
    out.loc[~known, "unit"] = "UNVERIFIED_PROVIDER_UNIT"
    out["definition_review"] = out.semantic_status.ne("DIRECT_EXISTING_FIELD")
    out["identity_review"] = out.identity_review | identity
    out["is_variant"] = out.definition_review | out.identity_review
    out["matrix_key"] = out.metric
    out.loc[out.definition_review, "matrix_key"] += "__lseg_" + code.loc[out.definition_review].map(previous.slug)
    out.loc[out.identity_review, "matrix_key"] += "__identity_review"
    out["matrix_eligible"] = known & out.ticker.notna()
    return out


def period_reference(raw):
    data = raw.copy()
    data["code"] = data.field.str.lower()
    data["period_end"] = pd.to_datetime(data.period_end, errors="coerce")
    data["announcement"] = pd.to_datetime(data.announcement_date, errors="coerce")
    valid = data.requested_fiscal_year.notna() & data.period_end.notna()
    data = data.loc[valid & data.code.isin(FLOW_CODES | BALANCE_ANCHORS)].copy()
    data["template"] = np.where(data.code.isin(FLOW_CODES), "TR.F.IncomeStatement", "TR.F.BalanceSheet")
    keys = ["ric", "requested_fiscal_year", "template"]
    ref = data.groupby(keys).period_end.agg(["nunique", "min"]).reset_index()
    ref["date"] = ref["min"].where(ref["nunique"].eq(1))
    ref["period_link_status"] = np.where(ref["nunique"].eq(1), "UNIQUE_ACTUAL_PERIOD_REFERENCE", "AMBIGUOUS_PERIOD_REFERENCE")
    pubs = data.loc[data.code.isin(["tr.isoriginalannouncementdate", "tr.bsoriginalannouncementdate"])
                    & data.announcement.ge(data.period_end)]
    pubs = pubs.groupby(keys + ["period_end"], as_index=False).announcement.min().rename(columns={"period_end": "date", "announcement": "published_at"})
    ref = ref.drop(columns=["min"]).merge(pubs, on=keys + ["date"], how="left", validate="one_to_one")
    return ref


def normalize_statement_rows(raw, reference):
    linked = raw.merge(reference, on=["ric", "requested_fiscal_year", "template"], how="left", validate="many_to_one")
    out = pd.DataFrame(index=linked.index)
    out["ticker"], out["ric"] = linked.ticker, linked.ric
    out["field"] = linked.provider_field
    out["metric"] = "pending"
    out["date"] = linked.date
    out["published_at"] = linked.published_at
    out["date_value"] = pd.NaT
    out["value"] = pd.to_numeric(linked.numeric_value, errors="coerce")
    out["kind"], out["provider"] = "number", "LSEG"
    out["unit"] = "UNVERIFIED_PROVIDER_UNIT"
    out["cik"], out["company"], out["accession"], out["form"] = "", "", "", ""
    out["identity_review"] = out.ticker.isin(["WFT", "XOM"])
    out["scope_review"], out["is_recovered"] = False, False
    out["annual_confirmed"] = linked.date.notna()
    out["period_link_status"] = linked.period_link_status.fillna("NO_ACTUAL_PERIOD_REFERENCE")
    out["source_rank"], out["concept_priority"] = 0, 0
    for name in ["requested_fiscal_year", "request_key", "parent_request_keys", "raw_value", "reporting_state_requested", "definition_id", "template"]:
        out[name] = linked[name]
    out["source_row"] = np.arange(len(out))
    return apply_field_rules(out), linked


def overlap_check(statements, raw):
    old = raw.loc[raw.numeric_value.notna() & raw.requested_fiscal_year.notna()].copy()
    old["code"] = old.field.str.lower()
    keys = ["ric", "requested_fiscal_year", "code"]
    ref = old.groupby(keys).numeric_value.agg(["min", "max"]).reset_index()
    ref = ref.loc[np.isclose(ref["min"], ref["max"], rtol=1e-8, atol=.01)]
    new = statements.copy()
    new["code"] = new.provider_field.str.lower()
    comparison = new.merge(ref, on=keys, how="inner", validate="many_to_one")
    comparison = comparison.loc[comparison.numeric_value.notna()].copy()
    comparison["matches_previous_request"] = np.isclose(comparison.numeric_value, comparison["min"], rtol=1e-6, atol=1.)
    return comparison


def attach_publications(data):
    # Full-statement dates are explicitly linked; direct financial amounts use
    # matching income/balance announcements. Never move an SEC filing backwards.
    mask = data.provider.eq("LSEG") & data.date.notna()
    pubs = data.loc[mask & ~data.identity_review & data.metric.isin(["balance_announcement", "income_announcement"])
                    & data.date_value.ge(data.date)]
    pubs = pubs.groupby(["ticker", "ric", "metric", "date"], as_index=False).date_value.min()
    pubs = pubs.rename(columns={"metric": "publication_type", "date_value": "matched_publication"})
    financial = mask & data.matrix_eligible & data.kind.eq("number") & data.metric.ne("market_cap") & data.published_at.isna()
    sample = data.loc[financial, ["row_id", "ticker", "ric", "metric", "date"]].copy()
    sample["publication_type"] = np.where(sample.metric.isin(FLOW_METRICS), "income_announcement", "balance_announcement")
    sample = sample.merge(pubs, on=["ticker", "ric", "publication_type", "date"], how="left", validate="many_to_one")
    lookup = sample.set_index("row_id").matched_publication
    data.loc[financial, "published_at"] = data.loc[financial, "row_id"].map(lookup).to_numpy()
    return data


def verify_matrices(output, catalog, selected, universe):
    total = 0
    for row in catalog.itertuples():
        matrix = pd.read_parquet(output / row.file)
        publication = pd.read_parquet(output / "Publication_Dates" / (row.metric + ".parquet"))
        assert matrix.columns.tolist() == universe
        assert matrix.index.is_unique and matrix.index.is_monotonic_increasing
        assert matrix.index.equals(publication.index) and matrix.columns.equals(publication.columns)
        assert int(matrix.notna().to_numpy().sum()) == row.observed_cells
        total += row.observed_cells
    assert total == len(selected)
    for key, sample in selected.sample(min(150, len(selected)), random_state=23).groupby("matrix_key"):
        folder = "Variants" if sample.is_variant.any() else "Matrices"
        matrix = pd.read_parquet(output / folder / (key + ".parquet"))
        for r in sample.itertuples():
            actual = matrix.loc[r.date, r.ticker]
            assert actual == (r.date_value if r.kind == "date" else r.value)


def run():
    started = time.perf_counter()
    token = uuid.uuid4().hex[:8]
    staging = BASE / ("Consolidated_staging_" + token)
    staging.mkdir()
    report_stage = staging / "QA"
    report_stage.mkdir()
    universe = pd.read_csv(previous.UNIVERSE).ticker.tolist()
    mapping_path = BASE / "ticker_cik_mapping.csv"
    mapping = pd.read_csv(mapping_path, dtype={"cik": str})
    links = mapping.loc[mapping.mapping_status.eq("SINGLE_CIK_CANDIDATE"), ["ticker", "cik"]].drop_duplicates()
    links = links.loc[links.ticker.isin(universe)]
    inventory, parts, raw_lseg = [], [], []
    def register(path, rows, category):
        inventory.append({"path": path.relative_to(ROOT).as_posix(), "sha256": previous.file_hash(path), "rows": int(rows), "category": category})
    for path in previous.SEC_INPUTS:
        print("Read", path.relative_to(ROOT), flush=True)
        data, count = previous.load_sec(path, links)
        data["input_file"] = path.relative_to(ROOT).as_posix()
        data["input_rank"] = len(inventory)
        data["semantic_status"] = np.where(data.scope_review, "EXISTING_SCOPE_REVIEW", "SEC_REPORTED_CONCEPT")
        parts.append(data)
        register(path, count, "SEC_annual_facts_with_vintages")
    lseg_paths = previous.LSEG_INPUTS + [COMPLETION / "observations.csv", COMPLETION / "identity_candidate_observations.csv"]
    for path in lseg_paths:
        print("Read", path.relative_to(ROOT), flush=True)
        identity = path.name == "identity_candidate_observations.csv"
        raw = pd.read_csv(path, low_memory=False)
        if not identity:
            raw_lseg.append(raw)
        data, count = previous.load_lseg(path, {"WFT", "XOM"})
        data = apply_field_rules(data, identity=identity)
        data["input_file"] = path.relative_to(ROOT).as_posix()
        data["input_rank"] = len(inventory)
        parts.append(data)
        register(path, count, "LSEG_identity_review" if identity else "LSEG_direct_and_alternative_fields")
    raw = pd.concat(raw_lseg, ignore_index=True)
    statement_path = RETRY / "statement_rows.csv"
    print("Read", statement_path.relative_to(ROOT), flush=True)
    statements = pd.read_csv(statement_path, low_memory=False)
    reference = period_reference(raw)
    extra, linked = normalize_statement_rows(statements, reference)
    comparison = overlap_check(statements, raw)
    bad_requests = set(comparison.loc[~comparison.matches_previous_request, "request_key"])
    extra.loc[extra.request_key.isin(bad_requests), "scope_review"] = True
    extra.loc[extra.request_key.isin(bad_requests), "matrix_key"] += "__source_value_mismatch"
    extra.loc[extra.request_key.isin(bad_requests), "is_variant"] = True
    extra["input_file"] = statement_path.relative_to(ROOT).as_posix()
    extra["input_rank"] = len(inventory)
    register(statement_path, len(statements), "LSEG_single_company_whole_statements")
    parts.append(extra)
    comparison.to_parquet(report_stage / "same_field_overlap_check.parquet", index=False)
    reference.to_parquet(staging / "statement_period_reference.parquet", index=False)
    linked[["ticker", "ric", "template", "requested_fiscal_year", "request_key", "date", "published_at", "period_link_status"]].drop_duplicates().to_parquet(report_stage / "statement_date_links.parquet", index=False)
    definitions = []
    for path in [COMPLETION / "field_definitions.csv", RETRY / "field_definitions.csv"]:
        frame = pd.read_csv(path)
        frame["input_file"] = path.relative_to(ROOT).as_posix()
        definitions.append(frame)
        register(path, len(frame), "provider_field_definitions")
    pd.concat(definitions, ignore_index=True).to_parquet(staging / "provider_field_definitions.parquet", index=False)
    register(mapping_path, len(mapping), "SEC_ticker_CIK_candidates")
    print("Normalize all observations and assess timing", flush=True)
    data = pd.concat(parts, ignore_index=True)
    data["row_id"] = np.arange(len(data))
    data = attach_publications(data)
    data["publication_before_period_end"] = data.published_at.notna() & data.date.notna() & data.published_at.lt(data.date)
    bad_time = data.publication_before_period_end
    data.loc[bad_time, "scope_review"] = True
    data.loc[bad_time, "matrix_key"] += "__publication_date_review"
    data.loc[bad_time, "is_variant"] = True
    for name in data.select_dtypes(include=["object", "str"]).columns:
        data[name] = data[name].astype("string")
    selected, differences, eligible_count = previous.select_cells(data)
    for name in ["Matrices", "Variants", "Publication_Dates"]:
        (staging / name).mkdir()
    print("Write unified archive and matrices", flush=True)
    data.to_parquet(staging / "observations_all.parquet", index=False)
    selected.to_parquet(staging / "selected_observations.parquet", index=False)
    differences.to_parquet(staging / "source_and_version_differences.parquet", index=False)
    data.loc[~data.matrix_eligible | data.ticker.isna()].to_parquet(staging / "unassigned_observations.parquet", index=False)
    catalog = []
    for key, group in selected.groupby("matrix_key", sort=True):
        variant, kind = bool(group.is_variant.any()), group.kind.iloc[0]
        folder = "Variants" if variant else "Matrices"
        value = "date_value" if kind == "date" else "value"
        matrix = group.pivot(index="date", columns="ticker", values=value).sort_index().reindex(columns=universe)
        matrix.index.name, matrix.columns.name = "date", "ticker"
        filename = folder + "/" + key + ".parquet"
        matrix.to_parquet(staging / filename)
        dates = group.pivot(index="date", columns="ticker", values="published_at").sort_index().reindex(index=matrix.index, columns=universe)
        dates.index.name, dates.columns.name = "date", "ticker"
        dates.to_parquet(staging / "Publication_Dates" / (key + ".parquet"))
        catalog.append({"metric": key, "file": filename, "variant": variant, "kind": kind,
                        "unit": "|".join(sorted(group.unit.dropna().unique())), "dates": len(matrix), "ticker_columns": len(universe),
                        "observed_cells": int(matrix.notna().to_numpy().sum()), "tickers_with_values": int(matrix.notna().any().sum()),
                        "first_date": str(matrix.index.min().date()), "last_date": str(matrix.index.max().date()),
                        "cells_without_publication_date": int(group.published_at.isna().sum())})
    catalog = pd.DataFrame(catalog)
    catalog.to_csv(staging / "dataset_catalog.csv", index=False)
    rules = pd.DataFrame([{"provider_field": code, "metric": rule[0], "unit": rule[1], "semantic_status": rule[2]} for code, rule in FIELD_RULES.items()])
    rules.to_csv(staging / "field_mapping_rules.csv", index=False)
    by_field = data.loc[data.provider.eq("LSEG")].groupby(["field", "metric", "semantic_status"], dropna=False).size().rename("source_rows").reset_index()
    by_field.to_csv(report_stage / "field_semantic_review.csv", index=False)
    print("Verify saved matrices and source hashes", flush=True)
    verify_matrices(staging, catalog, selected, universe)
    for item in inventory:
        assert previous.file_hash(ROOT / item["path"]) == item["sha256"], item["path"]
    # Retain previously calculated candidates separately, not as source facts.
    derived_path = RETRY / "derived_cost_candidates_linked.parquet"
    if derived_path.exists():
        shutil.copy2(derived_path, staging / "derived_cost_candidates.parquet")
        register(derived_path, len(pd.read_parquet(derived_path)), "calculation_candidates_not_source_observations")
    manifest = {"build": "2026-11-23", "inputs": inventory, "total_archived_rows": len(data), "selected_cells": len(selected),
                "primary_matrices": int((~catalog.variant).sum()), "variant_matrices": int(catalog.variant.sum()), "ticker_columns": len(universe),
                "eligible_source_rows": eligible_count, "overlap_comparisons": len(comparison),
                "overlap_matches": int(comparison.matches_previous_request.sum()), "overlap_mismatches": int((~comparison.matches_previous_request).sum()),
                "publication_before_period_rows": int(bad_time.sum()), "elapsed_seconds": round(time.perf_counter() - started, 2)}
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme = '''# Consolidated SEC and LSEG company inputs

Matrices contain actual fiscal-period dates as rows and all 900 historical
project tickers as columns. Market cap uses actual observation dates. Missing
values remain NaN; no daily filling, currency conversion or factor calculation.

Matrices/: existing direct definitions. Variants/: alternate fields, distinct
economic quantities, components, uncertain annual periods, currencies and issuer
identities. Read field_mapping_rules.csv before combining any variants.
Publication_Dates/: publication dates aligned to selected matrix cells.
observations_all.parquet: every loaded version and source record, with provenance.
selected_observations.parquet: exact selected record for each matrix cell.
unassigned_observations.parquet: unknown field roles/issuer links, retained but
not incorrectly promoted to a named financial parameter.
source_and_version_differences.parquet: differences, including ordinary revisions.
provider_field_definitions.parquet: full provider definitions.
statement_period_reference.parquet: explicitly observed fiscal ends matched to
full statements by RIC, FY request label and statement type; no guessed Dec 31.
derived_cost_candidates.parquet: separately calculated candidates, not downloads.
QA/: exact-field overlap comparison, statement/date linkage and semantic review.

Selection prefers direct LSEG Orig-request values, then native SEC facts, then
recovered SEC values. Known publication dates and earliest SEC filing versions
are preferred within a source. All other versions remain in the archive.

Technical consistency does not certify historical economic correctness. Orig is
a request, not independent PIT verification. Whole-statement period linkage is
documented cross-reference, not a directly returned per-field date. Day-only
announcements require execution lag. Filing/source differences may be revisions.

TR.F.MinIntr is minority earnings; it is not balance-sheet minority equity.
TR.F.CostOfOpRev can include financing costs and is not universally COGS.
TR.F.IntrExpn is net interest and is not automatically gross interest expense.
Parent, common, tangible, hybrid-inclusive and preferred equity remain distinct.
Partial expenses, EBIT and income before tax never fill revenue/SGA/COGS cells.
These distinctions can change candidate-coverage percentages from older reports.

All extraction stages received through the single-company retries are included.
No network extraction was performed and no source download was altered.
'''
    (staging / "README.md").write_text(readme, encoding="utf-8")
    summary = ["# Consolidated company-data verification", "", f"Build: {manifest['build']}",
        f"Main matrices: {manifest['primary_matrices']}; variant matrices: {manifest['variant_matrices']}; columns per matrix: 900.",
        f"Source rows archived (including versions/repeats): {len(data):,}; selected cells: {len(selected):,}.",
        f"Exact-field numeric comparisons: {len(comparison):,}; matches: {manifest['overlap_matches']:,}; mismatches: {manifest['overlap_mismatches']:,}.", "",
        "PASS: matrix shapes, date ordering, unique axes, publication alignment, cell counts, source-record samples and source hashes.",
        "REVIEW: issuer candidates, alternate economic definitions, day-only announcements, field-period cross-references and source/filing revisions.",
        "Different quantities and partial components were retained separately. This is not a declaration that every number is economically validated or that FF5 is ready."]
    (report_stage / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    # Verify resolved absolute paths before moving whole directories on Windows.
    archive = BASE / "Consolidated_Archive" / ("previous_" + token)
    assert TARGET.resolve().parent == BASE.resolve()
    assert staging.resolve().parent == BASE.resolve()
    assert archive.resolve().parent.parent == BASE.resolve()
    if TARGET.exists():
        if not (TARGET / "manifest.json").is_file():
            raise RuntimeError("Refusing to archive a target without a consolidation manifest.")
        archive.parent.mkdir(exist_ok=True)
        TARGET.rename(archive)
    try:
        staging.rename(TARGET)
    except BaseException:
        if archive.exists() and not TARGET.exists():
            archive.rename(TARGET)
        raise
    REPORT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET / "QA/summary.md", REPORT / "summary.md")
    catalog.to_csv(REPORT / "dataset_catalog.csv", index=False)
    print(json.dumps(manifest, indent=2), flush=True)
    print("Current dataset:", TARGET, flush=True)
    print("Previous snapshot:", archive, flush=True)


if __name__ == "__main__":
    run()
