"""One-off offline consolidation of downloaded FF company inputs; no network.

Matrices use actual fiscal period ends (market cap: actual observation dates).
All versions/definitions stay in observations_all.parquet. Main matrix selection
prefers dated, original-request LSEG fields, then the earliest SEC filing and
native concepts before recovered amounts. Alternatives remain distinct matrices.
This is storage consolidation, not certified FF eligibility or a PIT backtest.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Data/Fama and french"
OUTPUT = SOURCE / "Consolidated"
REPORT = ROOT / "Results/Fama_French/Consolidation"
UNIVERSE = ROOT / "Data/Data_System/Raw/universe.csv"
SEC_INPUTS = [
    SOURCE / "Processed/annual_facts_all_versions.parquet",
    SOURCE / "Refined/annual_facts_all_versions.parquet",
    SOURCE / "Online/filing_observations.parquet",
]
LSEG_INPUTS = [
    ROOT / "External_Tools/LSEG/lseg_company_data_output/observations.csv",
    ROOT / "LSEG_Recovery/lseg_company_recovery_output/observations.csv",
    ROOT / "LSEG_Recovery/lseg_company_recovery_output/alternative_observations.csv",
]
METRIC_MAP = {"common_equity_provider": "common_equity", "cost_of_sales_provider": "cost_of_sales",
              "interest_expense_provider": "interest_expense", "total_equity_provider": "total_equity_lseg_provider",
              "minority_interest_provider": "minority_interest"}


def flags(series):
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "1.0"])


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def series(frame, name, default=""):
    return frame[name] if name in frame else pd.Series(default, index=frame.index)


def load_sec(path, links):
    raw = pd.read_parquet(path)
    raw["source_row"] = np.arange(len(raw))
    # Multiple CIK candidates cannot be silently assigned to a historical symbol.
    frame = raw.merge(links[["ticker", "cik"]], on="cik", how="left", validate="many_to_many")
    out = pd.DataFrame(index=frame.index)
    for name in ["ticker", "cik", "company", "metric", "unit", "accession", "form", "source_row"]:
        out[name] = series(frame, name)
    out["field"] = series(frame, "taxonomy").astype(str) + ":" + series(frame, "concept").astype(str)
    out["date"] = pd.to_datetime(frame.period_end, errors="coerce")
    out["value"] = pd.to_numeric(frame.value, errors="coerce")
    out["date_value"] = pd.NaT
    out["published_at"] = pd.to_datetime(frame.filed, errors="coerce")
    out["provider"] = "SEC"
    out["ric"] = ""
    out["concept_priority"] = pd.to_numeric(series(frame, "concept_priority", 999), errors="coerce").fillna(999)
    out["scope_review"] = flags(series(frame, "scope_review_required", False)) | flags(series(frame, "custom_label_review_required", False))
    out["annual_confirmed"] = flags(series(frame, "annual_period_confirmed", False))
    out["identity_review"] = False
    out["definition_review"] = out.scope_review
    rule = series(frame, "recovery_rule").fillna("").astype(str)
    out["is_recovered"] = ~rule.isin(["", "reported_source", "nan", "None", "<NA>"])
    out["recovery_rule"] = series(frame, "recovery_rule")
    out["source_components"] = series(frame, "source_components").map(lambda v: json.dumps(v, default=str) if isinstance(v, (list, dict, tuple, np.ndarray)) else str(v))
    out["reporting_state_requested"] = "SEC_FILING_VINTAGE"
    out["kind"] = "number"
    out["matrix_key"] = out.metric
    out.loc[out.scope_review, "matrix_key"] += "__scope_review"
    out.loc[~out.annual_confirmed, "matrix_key"] += "__annual_period_review"
    # Preserve other currencies separately instead of mixing or guessing FX rates.
    foreign = ~out.unit.isin(["USD", "shares"])
    out.loc[foreign, "matrix_key"] += "__" + out.loc[foreign, "unit"].map(slug)
    out["is_variant"] = out.scope_review | ~out.annual_confirmed | foreign
    out["source_rank"] = np.where(out.is_recovered, 2, 1)
    # Custom concepts with no economic assignment stay in the archive.
    out["matrix_eligible"] = out.metric.ne("custom_scope_review") & out.ticker.notna()
    for name in ["period_start", "period_year", "duration_days", "filing_fiscal_year", "filing_fiscal_period",
                 "frame", "source_label", "source_url", "extraction_basis"]:
        out[name] = series(frame, name)
    return out, len(raw)


def load_lseg(path, identity_review):
    frame = pd.read_csv(path, low_memory=False)
    out = pd.DataFrame(index=frame.index)
    out["ticker"] = frame.ticker
    out["ric"] = frame.ric
    out["cik"], out["company"], out["accession"], out["form"] = "", "", "", ""
    target = series(frame, "target_metric").replace("", np.nan).fillna(frame.metric)
    out["metric"] = target.map(lambda x: METRIC_MAP.get(x, x))
    out["field"] = frame.field
    out["date"] = pd.to_datetime(frame.period_end, errors="coerce")
    cap = frame.metric.eq("market_cap")
    out.loc[cap, "date"] = pd.to_datetime(frame.loc[cap, "observation_date"], errors="coerce")
    isdate = out.metric.isin(["balance_announcement", "income_announcement"])
    out["value"] = pd.to_numeric(frame.numeric_value, errors="coerce")
    out["date_value"] = pd.to_datetime(frame.announcement_date, errors="coerce")
    out.loc[~isdate, "date_value"] = pd.NaT
    out["published_at"] = pd.NaT
    out.loc[isdate, "published_at"] = out.loc[isdate, "date_value"]
    out.loc[cap, "published_at"] = out.loc[cap, "date"]
    out["kind"] = np.where(isdate, "date", "number")
    out["unit"] = np.where(isdate, "date", "USD")
    out["provider"] = "LSEG"
    out["definition_review"] = flags(series(frame, "definition_review_required", False))
    out["identity_review"] = out.ticker.isin(identity_review)
    out["scope_review"] = False
    out["annual_confirmed"] = True
    out["is_recovered"] = False
    out["recovery_rule"], out["source_components"] = "", ""
    out["concept_priority"] = 0
    out["source_row"] = np.arange(len(frame))
    out["request_key"] = frame.request_key
    out["requested_fiscal_year"] = frame.requested_fiscal_year
    out["raw_value"] = frame.raw_value
    out["reporting_state_requested"] = frame.reporting_state_requested
    out["matrix_key"] = out.metric
    alternative = out.definition_review
    out.loc[alternative, "matrix_key"] += "__lseg_" + out.loc[alternative, "field"].map(slug)
    out.loc[out.identity_review, "matrix_key"] += "__identity_review"
    out["is_variant"] = alternative | out.identity_review
    out["source_rank"] = 0
    out["matrix_eligible"] = True
    return out, len(frame)


def attach_lseg_publication_dates(data):
    lseg = data.provider.eq("LSEG")
    ispub = data.metric.isin(["balance_announcement", "income_announcement"])
    dates = data.loc[lseg & ispub & data.date_value.ge(data.date)]
    dates = dates.groupby(["ticker", "ric", "metric", "date"], as_index=False).date_value.min()
    dates = dates.rename(columns={"metric": "publication_type", "date_value": "matched_publication"})
    financial = lseg & ~ispub & data.metric.ne("market_cap")
    sample = data.loc[financial, ["row_id", "ticker", "ric", "metric", "date"]].copy()
    sample["publication_type"] = np.where(sample.metric.isin(["revenue", "cost_of_sales", "sga", "interest_expense"]), "income_announcement", "balance_announcement")
    sample = sample.merge(dates, on=["ticker", "ric", "publication_type", "date"], how="left", validate="many_to_one")
    lookup = sample.set_index("row_id").matched_publication
    data.loc[financial, "published_at"] = data.loc[financial, "row_id"].map(lookup).to_numpy()
    return data


def select_cells(data):
    valid_number = data.kind.eq("number") & np.isfinite(data.value)
    valid_date = data.kind.eq("date") & data.date_value.notna()
    eligible = data.matrix_eligible & data.ticker.notna() & data.date.notna() & (valid_number | valid_date)
    frame = data.loc[eligible].copy()
    frame["missing_publication"] = frame.published_at.isna()
    # Stable, documented selection; no averaging and no latest-restatement fill.
    frame = frame.sort_values(["matrix_key", "date", "ticker", "source_rank", "missing_publication",
                               "published_at", "concept_priority", "is_recovered", "input_rank", "row_id"], kind="stable")
    keys = ["matrix_key", "date", "ticker"]
    selected = frame.drop_duplicates(keys, keep="first").copy()
    frame["value_key"] = np.where(frame.kind.eq("date"), frame.date_value.astype(str), frame.value.astype(str))
    groups = frame.groupby(keys, sort=False).value_key.nunique()
    conflict_keys = groups.loc[groups.gt(1)].rename("distinct_values").reset_index()
    conflicts = frame.merge(conflict_keys, on=keys, how="inner", validate="many_to_one")
    conflicts["difference_type"] = "SOURCE_OR_FILING_VERSION_DIFFERENCE"
    return selected, conflicts, int(eligible.sum())


def run(refresh=False):
    started = time.perf_counter()
    if OUTPUT.exists() and any(OUTPUT.iterdir()) and not refresh:
        raise RuntimeError(f"Output already contains files: {OUTPUT}. Refusing to overwrite an existing consolidation.")
    universe = pd.read_csv(UNIVERSE).ticker.tolist()
    mapping = pd.read_csv(SOURCE / "ticker_cik_mapping.csv", dtype={"cik": str})
    links = mapping.loc[mapping.mapping_status.eq("SINGLE_CIK_CANDIDATE"), ["ticker", "cik"]].drop_duplicates()
    links = links.loc[links.ticker.isin(universe)]
    review_path = ROOT / "LSEG_Recovery/lseg_company_recovery_output/identity_mismatches_review.csv"
    identity_review = set(pd.read_csv(review_path).ticker) if review_path.exists() else set()
    inventory, parts = [], []
    for rank, path in enumerate(SEC_INPUTS + LSEG_INPUTS):
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"Read {path.relative_to(ROOT)}", flush=True)
        original_hash = file_hash(path)
        out, source_rows = load_sec(path, links) if path.suffix == ".parquet" else load_lseg(path, identity_review)
        out["input_file"] = path.relative_to(ROOT).as_posix()
        out["input_rank"] = rank
        inventory.append({"path": path.relative_to(ROOT).as_posix(), "sha256": original_hash,
                          "source_rows": source_rows, "linked_rows": len(out)})
        parts.append(out)
    print("Combine source observations and publication dates", flush=True)
    data = pd.concat(parts, ignore_index=True)
    data["row_id"] = np.arange(len(data))
    data = attach_lseg_publication_dates(data)
    # Uniform string metadata avoids mixed-object Arrow columns.
    for column in data.select_dtypes(include=["object", "str"]).columns:
        data[column] = data[column].astype("string")
    selected, conflicts, eligible_rows = select_cells(data)
    for directory in [OUTPUT / "Matrices", OUTPUT / "Variants", OUTPUT / "Publication_Dates", REPORT]:
        directory.mkdir(parents=True, exist_ok=True)
    data.to_parquet(OUTPUT / "observations_all.parquet", index=False)
    selected.to_parquet(OUTPUT / "selected_observations.parquet", index=False)
    conflicts.to_parquet(OUTPUT / "source_and_version_differences.parquet", index=False)
    unmatched = data.loc[~data.matrix_eligible | data.ticker.isna()]
    unmatched.to_parquet(OUTPUT / "unassigned_observations.parquet", index=False)
    descriptions = []
    for key, group in selected.groupby("matrix_key", sort=True):
        if not set(group.ticker).issubset(universe):
            raise AssertionError(f"Unknown ticker in {key}")
        variant = bool(group.is_variant.any())
        kind = group.kind.iloc[0]
        value_column = "date_value" if kind == "date" else "value"
        matrix = group.pivot(index="date", columns="ticker", values=value_column).sort_index().reindex(columns=universe)
        matrix.index.name, matrix.columns.name = "date", "ticker"
        folder = "Variants" if variant else "Matrices"
        filename = folder + "/" + key + ".parquet"
        matrix.to_parquet(OUTPUT / filename)
        publication = group.pivot(index="date", columns="ticker", values="published_at").sort_index().reindex(index=matrix.index, columns=universe)
        publication.index.name, publication.columns.name = "date", "ticker"
        publication.to_parquet(OUTPUT / "Publication_Dates" / (key + ".parquet"))
        cells = int(matrix.notna().to_numpy().sum())
        assert cells == len(group)
        assert matrix.columns.tolist() == universe and matrix.index.is_unique and matrix.index.is_monotonic_increasing
        descriptions.append({"metric": key, "file": filename, "variant": variant, "kind": kind,
                             "unit": "|".join(sorted(group.unit.dropna().unique())), "dates": len(matrix), "ticker_columns": len(universe),
                             "observed_cells": cells, "tickers_with_values": int(matrix.notna().any().sum()),
                             "first_date": matrix.index.min().date().isoformat(), "last_date": matrix.index.max().date().isoformat(),
                             "cells_without_publication_date": int(group.published_at.isna().sum())})
    catalog = pd.DataFrame(descriptions)
    catalog.to_csv(OUTPUT / "dataset_catalog.csv", index=False)
    catalog.to_csv(REPORT / "dataset_catalog.csv", index=False)
    for item in inventory:
        if file_hash(ROOT / item["path"]) != item["sha256"]:
            raise AssertionError("An input changed during consolidation: " + item["path"])
    manifest = {"inputs": inventory, "total_archived_rows": len(data), "selected_cells": len(selected),
                "eligible_source_rows": eligible_rows, "difference_rows": len(conflicts), "unassigned_rows": len(unmatched),
                "primary_matrices": int((~catalog.variant).sum()), "variant_matrices": int(catalog.variant.sum()),
                "ticker_columns": len(universe), "elapsed_seconds": round(time.perf_counter() - started, 2)}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    text = """# Consolidated company-data matrices

Each dataset contains dates as rows, all 900 historical project tickers as columns,
and reported values as cells. Matrices use actual fiscal period ends; market cap
uses actual provider observation dates. Missing cells remain NaN. No forward fill,
resampling, currency conversion, factor calculation or source-file replacement.

Matrices/: original metric definitions, combined across sources where appropriate.
Variants/: alternative LSEG fields, scope-review concepts, uncertain annual periods,
non-USD values and explicitly flagged identity conflicts. These remain available
but do not silently replace a differently defined main parameter.
Publication_Dates/: publication/filing dates aligned to each selected matrix cell.
For market cap this is the observation date, not a verified vendor release timestamp.
dataset_catalog.csv: complete dataset inventory, shapes, units and observed counts.
observations_all.parquet: every loaded source version, including SEC concepts,
filing dates, accession IDs, RICs, request keys and input-file provenance.
selected_observations.parquet: exact source record chosen for every matrix cell.
source_and_version_differences.parquet: different reported values for the same
parameter/date/ticker; includes ordinary revisions, not only suspected errors.
unassigned_observations.parquet: observations without an unambiguous ticker link
or economic metric assignment; kept rather than attached to an arbitrary company.

Selection prefers direct LSEG fields requested as Orig, then SEC native facts,
then recovered SEC amounts. Within a source, known publication dates and the
earliest filing are preferred; concept priority resolves competing SEC concepts.
Values are never averaged across sources. Reported differences remain archived.

These are consolidated source candidates, not certified Fama-French inputs.
Common equity, parent equity, total equity and minority-inclusive equity remain
separate metrics. Bank revenue and modern expense alternatives remain variants.
All raw filing vintages are retained because one wide cell cannot represent all
restatements. Publication-date matrices and the long archive must be used for
point-in-time research. A provider Orig request is not independent verification
of a historical vintage, and day-only announcement dates require execution lag.
The matrices are not daily, point-in-time factor-ready feature panels.

No completion-stage extraction has been received yet. This build includes the
SEC Companyfacts/refinement/original-filing results, first full LSEG extraction,
and first LSEG recovery including its alternative field candidates.
"""
    (OUTPUT / "README.md").write_text(text, encoding="utf-8")
    summary = ["# Consolidation of downloaded company data", "",
               f"Primary matrices: **{manifest['primary_matrices']}**; variant matrices: **{manifest['variant_matrices']}**.",
               f"Every matrix has **{len(universe)} ticker columns**. Selected non-missing cells: **{len(selected):,}**.",
               f"Source observations retained: **{len(data):,}**. Elapsed: **{manifest['elapsed_seconds']} seconds**.", "",
               "All input hashes were rechecked and remain unchanged. No online extraction was launched.", "",
               "| Parameter | Observed cells | Tickers with values |", "|---|---:|---:|"]
    for row in catalog.loc[~catalog.variant].itertuples():
        summary.append(f"| {row.metric} | {row.observed_cells:,} | {row.tickers_with_values} |")
    summary += ["", "See Data/Fama and french/Consolidated/README.md for selection, dates and source-version interpretation.",
                "Observed counts are not percentages of FF portfolio eligibility."]
    (REPORT / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    run(refresh="--refresh" in sys.argv)
