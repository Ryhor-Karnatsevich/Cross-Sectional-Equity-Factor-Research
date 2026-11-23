"""Offline accept/reject audit of downloaded company inputs. No network or models.

Publishes only accepted observations, after archiving the consolidated candidate
snapshot. Rejected source rows remain in that immutable audit snapshot, never in
the active matrices. Acceptance is against the documented data contract; it is
not a guarantee that a data vendor or an audited filing contains no error.
"""
from pathlib import Path
import hashlib
import json
import re
import time
import uuid

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Data/Fama and french"
TARGET = BASE / "Consolidated"
REPORT = ROOT / "Results/Fama_French/Final_Validation"

# These are total measures under the original extraction's definitions. Modern
# fields with broader cost/revenue scope are not substitutions for legacy fields.
LSEG_FIELDS = {
    "tr.totalassetsreported": "total_assets",
    "tr.totalrevenue": "revenue",
    "tr.costofrevenuetotal": "cost_of_sales",
    "tr.sgaexpensetotal": "sga",
    "tr.interestexpense": "interest_expense",
    "tr.f.shholdeqcom": "common_equity",
    "tr.companymarketcap": "market_cap",
    "tr.bsoriginalannouncementdate": "balance_announcement",
    "tr.isoriginalannouncementdate": "income_announcement",
    # The reviewed definition is total assets. Disagreeing amounts are excluded
    # below instead of treating the two field codes as automatically equivalent.
    "tr.f.totassets": "total_assets",
}
SEC_FIELDS = {
    "us-gaap:Assets": "total_assets",
    "ifrs-full:Assets": "total_assets",
    "us-gaap:CommonStockholdersEquity": "common_equity",
    "us-gaap:Revenues": "revenue",
    "us-gaap:SalesRevenueNet": "revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "ifrs-full:Revenue": "revenue",
    "us-gaap:CostOfGoodsAndServicesSold": "cost_of_sales",
    "us-gaap:CostOfRevenue": "cost_of_sales",
    "ifrs-full:CostOfSales": "cost_of_sales",
    "us-gaap:SellingGeneralAndAdministrativeExpense": "sga",
    "us-gaap:InterestExpense": "interest_expense",
    "us-gaap:InterestAndDebtExpense": "interest_expense",
    # Ancillary quantities retain their own names; they are not filled into
    # total expenses or common equity and do not count as complete FF inputs.
    "us-gaap:CostOfGoodsSold": "cost_of_goods_component",
    "us-gaap:InterestExpenseNonoperating": "interest_nonoperating_component",
    "us-gaap:CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization": "cost_of_sales_excluding_da",
    "us-gaap:CostOfServices": "cost_of_services_component",
    "us-gaap:DeferredIncomeTaxesAndTaxCredits": "deferred_tax_and_credits",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "equity_including_minority",
    "ifrs-full:Equity": "equity_including_minority",
    "us-gaap:StockholdersEquity": "equity_parent",
    "ifrs-full:EquityAttributableToOwnersOfParent": "equity_parent",
    "us-gaap:GeneralAndAdministrativeExpense": "general_administrative",
    "us-gaap:GrossProfit": "gross_profit",
    "ifrs-full:GrossProfit": "gross_profit",
    "us-gaap:InterestExpenseDebt": "interest_debt_component",
    "us-gaap:MinorityInterest": "minority_interest",
    "ifrs-full:NoncontrollingInterests": "minority_interest",
    "us-gaap:PreferredStockValue": "preferred_equity",
    "us-gaap:SalesRevenueGoodsNet": "revenue_goods",
    "us-gaap:SalesRevenueServicesNet": "revenue_services",
    "us-gaap:SellingAndMarketingExpense": "selling_marketing",
    "us-gaap:SellingExpense": "selling_only",
    "us-gaap:CommonStockSharesOutstanding": "shares_outstanding",
    "dei:EntityCommonStockSharesOutstanding": "shares_outstanding",
}
FLOW = {"revenue", "cost_of_sales", "sga", "interest_expense", "cost_of_goods_component",
        "interest_nonoperating_component", "cost_of_sales_excluding_da", "cost_of_services_component",
        "general_administrative", "gross_profit", "interest_debt_component", "revenue_goods",
        "revenue_services", "selling_marketing", "selling_only"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def name_key(value):
    # Exact normalized legal name, not a loose match on a single shared word.
    words = re.findall(r"[a-z0-9]+", str(value).lower().replace("&", " and "))
    remove = {"inc", "incorporated", "corp", "corporation", "co", "company", "limited", "ltd",
              "plc", "the", "de", "md", "nv", "sa"}
    return " ".join(w for w in words if w not in remove)


def identity_tables(source):
    sec = pd.read_csv(source / "ticker_cik_candidates.csv", dtype=str).fillna("")
    selected = pd.read_csv(source / "lseg_ticker_ric_candidates.csv", dtype=str).fillna("")
    ids = pd.read_csv(ROOT / "External_Tools/LSEG/lseg_company_data_output/identities.csv", dtype=str).fillna("")
    identity = ids.groupby("Instrument").agg(
        isins=("TR.ISIN", lambda x: sorted(set(x) - {""})),
        names=("TR.COMMONNAME", lambda x: sorted(set(x) - {""})),
    )
    universe = pd.read_csv(ROOT / "Data/Data_System/Raw/universe.csv", dtype=str).fillna("").set_index("ticker")
    ric_rows = []
    for row in selected.itertuples():
        matched = row.ric in identity.index and bool(row.isin) and identity.loc[row.ric, "isins"] == [row.isin]
        prior = universe.loc[row.ticker] if row.ticker in universe.index else None
        recovered_reference = prior is not None and prior.get("lseg_ric", "") == row.ric and prior.get("lseg_isin", "") == row.isin
        name_match = False
        if row.ric in identity.index:
            expected = {name_key(x) for x in row.company.split("|")} - {""}
            actual = {name_key(x) for x in identity.loc[row.ric, "names"]} - {""}
            name_match = bool(expected & actual)
        unique_search = row.mapping_status in {"UNIQUE_SECURITY_CANDIDATE_REVIEW", "NORMALIZED_NAME_SINGLE_SECURITY_CANDIDATE"}
        # Shared/successor RICs are not automatically approved by matching an ISIN.
        # Only direct renames already declared in config can share an issuer link.
        from src.Data_System.config import YAHOO_TICKER_ALIASES
        direct_rename = row.ticker in YAHOO_TICKER_ALIASES or row.ticker in YAHOO_TICKER_ALIASES.values()
        approved = matched and (name_match or recovered_reference) and (unique_search or
                   row.mapping_status == "EXISTING_MAPPING" or direct_rename)
        approved = approved and row.ticker not in {"WFT", "XOM"}
        ric_rows.append({"ticker": row.ticker, "ric": row.ric, "isin": row.isin,
                         "decision": "ACCEPT" if approved else "REJECT",
                         "reason": "EXACT_ISIN_AND_ISSUER_REFERENCE" if approved else "IDENTITY_OR_SUCCESSOR_CONTINUITY_NOT_ESTABLISHED"})
    rics = pd.DataFrame(ric_rows)
    expected_names = selected.groupby("ticker").company.agg(list).to_dict()
    sec_rows = []
    from src.Data_System.config import YAHOO_REUSED_TICKERS
    for row in sec.itertuples():
        names = expected_names.get(row.ticker, []) + row.historical_company_hints.split("|")
        name_match = name_key(row.sec_company) in {name_key(n) for n in names if n}
        single = row.mapping_status == "SINGLE_CIK_CANDIDATE" and bool(row.cik)
        approved = single and name_match and row.ticker not in (YAHOO_REUSED_TICKERS | {"WFT", "XOM"})
        sec_rows.append({"ticker": row.ticker, "cik": row.cik, "company": row.sec_company,
                         "decision": "ACCEPT" if approved else "REJECT",
                         "reason": "UNIQUE_CIK_AND_EXACT_ISSUER_NAME_REFERENCE" if approved else "CIK_ISSUER_OR_HISTORICAL_CONTINUITY_NOT_ESTABLISHED"})
    return rics, pd.DataFrame(sec_rows)


def request_parameters():
    paths = [ROOT / "External_Tools/LSEG/lseg_company_data_output/request_report.csv",
             ROOT / "LSEG_Recovery/lseg_company_recovery_output/request_report.csv",
             ROOT / "External_Tools/LSEG/lseg_company_completion_output/request_report.csv",
             ROOT / "External_Tools/LSEG/lseg_statement_retry_output/request_report.csv"]
    records = {}
    for path in paths:
        frame = pd.read_csv(path, dtype=str).fillna("")
        for key, params in frame[["request_key", "parameters"]].drop_duplicates().itertuples(index=False, name=None):
            try:
                value = json.loads(params)
            except (TypeError, ValueError):
                continue
            if key in records and records[key] != value:
                raise ValueError(f"Conflicting parameter provenance: {key}")
            records[key] = value
    return records


def run():
    started = time.perf_counter()
    # A rerun always uses the complete archived candidate snapshot, never the
    # already filtered output (otherwise excluded rows could disappear from QA).
    source = TARGET
    if (TARGET / "acceptance_contract.json").exists():
        source = Path(json.loads((TARGET / "acceptance_contract.json").read_text())["source_snapshot"])
    manifest = json.loads((source / "manifest.json").read_text())
    source_hash = digest(source / "observations_all.parquet")
    data = pd.read_parquet(source / "observations_all.parquet")
    universe = pd.read_csv(ROOT / "Data/Data_System/Raw/universe.csv").ticker.tolist()
    token = uuid.uuid4().hex[:8]
    staging = BASE / ("Final_staging_" + token)
    staging.mkdir()
    qa = staging / "QA"
    qa.mkdir()
    ric_ids, cik_ids = identity_tables(source)
    ric_ids.to_csv(qa / "ric_identity_decisions.csv", index=False)
    cik_ids.to_csv(qa / "cik_identity_decisions.csv", index=False)
    good_rics = set(ric_ids.loc[ric_ids.decision.eq("ACCEPT"), ["ticker", "ric"]].itertuples(index=False, name=None))
    good_ciks = set(cik_ids.loc[cik_ids.decision.eq("ACCEPT"), ["ticker", "cik"]].itertuples(index=False, name=None))
    params = request_parameters()
    print("Evaluate", len(data), "source rows", flush=True)
    reasons = pd.Series("", index=data.index, dtype="string")

    def reject(mask, reason):
        mask = mask.fillna(False)
        reasons.loc[mask] += reason + ";"

    lseg, sec = data.provider.eq("LSEG"), data.provider.eq("SEC")
    metrics = data.field.map(SEC_FIELDS)
    metrics.loc[lseg] = data.loc[lseg, "field"].str.lower().map(LSEG_FIELDS)
    reject(metrics.isna(), "FIELD_NOT_APPROVED_FOR_DECLARED_PARAMETER")
    data["accepted_metric"] = metrics
    reject(~data.ticker.isin(universe) | data.date.isna(), "UNKNOWN_TICKER_OR_UNOBSERVED_PERIOD")
    ric_ok = pd.Series(list(zip(data.ticker, data.ric)), index=data.index).isin(good_rics)
    cik_ok = pd.Series(list(zip(data.ticker, data.cik)), index=data.index).isin(good_ciks)
    reject((lseg & ~ric_ok) | (sec & ~cik_ok), "UNCONFIRMED_ISSUER_LINK")
    reject(data.scope_review | data.identity_review, "SOURCE_SCOPE_OR_IDENTITY_EXCEPTION")
    reject(~data.annual_confirmed & ~metrics.eq("market_cap"), "ANNUAL_PERIOD_NOT_ESTABLISHED")
    reject(data.kind.eq("number") & ~np.isfinite(data.value), "MISSING_OR_NONFINITE_NUMBER")
    reject(data.kind.eq("date") & data.date_value.isna(), "MISSING_DATE_VALUE")
    reject(~data.unit.isin(["USD", "shares", "date"]), "UNAPPROVED_CURRENCY_OR_UNIT")
    reject(data.published_at.isna() | data.published_at.lt(data.date), "MISSING_OR_IMPOSSIBLE_PUBLICATION_DATE")
    reject(data.date.gt(pd.Timestamp("2026-08-18")) | data.published_at.gt(pd.Timestamp("2026-08-18")), "AFTER_DATASET_CUTOFF")
    reject(metrics.isin(["total_assets", "market_cap", "shares_outstanding"]) & data.value.le(0), "NONPOSITIVE_SIZE_ASSET_OR_SHARE_COUNT")
    reject(sec & ~data.form.isin(["10-K", "10-K/A", "20-F", "20-F/A"]), "NONSTANDARD_OR_TRANSITION_ANNUAL_FILING")
    reject(sec & ~data.accession.fillna("").str.fullmatch(r"\d{10}-\d{2}-\d{6}"), "NO_INSPECTABLE_SEC_FILING_ACCESSION")
    duration = pd.to_numeric(data.duration_days, errors="coerce")
    reject(sec & metrics.isin(FLOW) & ~duration.between(330, 400), "UNVERIFIED_FULL_YEAR_FLOW_DURATION")
    reject(data.is_recovered, "DERIVED_AMOUNT_NOT_INDEPENDENTLY_RECONCILED")
    currency_ok, original_ok, annual_ok = {}, {}, {}
    for key, value in params.items():
        currency_ok[key] = value.get("Curn") == "USD" and str(value.get("Scale")) in {"0", "0.0"}
        original_ok[key] = value.get("ReportingState") == "Orig"
        annual_ok[key] = bool(re.fullmatch(r"FY\d{4}", str(value.get("Period", ""))))
    monetary = lseg & data.kind.eq("number")
    reject(monetary & ~data.request_key.map(currency_ok).fillna(False).astype(bool), "REQUEST_DOES_NOT_ESTABLISH_USD_UNSCALED_VALUE")
    annual_lseg = lseg & ~metrics.eq("market_cap")
    reject(annual_lseg & (~data.request_key.map(original_ok).fillna(False).astype(bool) |
                        ~data.request_key.map(annual_ok).fillna(False).astype(bool)), "ORIGINAL_FISCAL_YEAR_REQUEST_NOT_ESTABLISHED")
    # Orig/annual parameters and an observed exact fiscal date are required for
    # linked full statements. A requested FY label alone is never a period date.
    reject(lseg & data.template.notna() & ~data.period_link_status.eq("UNIQUE_ACTUAL_PERIOD_REFERENCE"),
           "UNIQUE_ACTUAL_STATEMENT_PERIOD_NOT_ESTABLISHED")

    # Conflicting repeated Orig responses for the same exact field/period cannot
    # be adjudicated by preferring the largest, newest or most convenient value.
    keys = ["ticker", "ric", "field", "date"]
    cand = data.loc[lseg & reasons.eq("") & data.kind.eq("number")]
    bounds = cand.groupby(keys).value.agg(["min", "max"])
    bad = bounds.loc[~np.isclose(bounds["min"], bounds["max"], rtol=1e-6, atol=1)].index
    reject(lseg & pd.Series(pd.MultiIndex.from_frame(data[keys]).isin(bad), index=data.index), "CONFLICTING_ORIGINAL_SAME_FIELD_VALUES")
    # The modern assets field is promoted only where its same-period value is
    # consistent with the established legacy field; gaps have no such evidence.
    legacy = data.loc[lseg & data.field.str.lower().eq("tr.totalassetsreported") & reasons.eq("")].groupby(["ticker", "date"]).value.first()
    modern = lseg & data.field.str.lower().eq("tr.f.totassets")
    lookup = pd.MultiIndex.from_frame(data[["ticker", "date"]])
    baseline = pd.Series(legacy.reindex(lookup).to_numpy(), index=data.index)
    reject(modern & (baseline.isna() | ~np.isclose(data.value, baseline, rtol=1e-6, atol=1)), "MODERN_ASSETS_NOT_RECONCILED_TO_SAME_PERIOD_DIRECT_FIELD")

    valid = data.loc[reasons.eq("")].copy()
    valid["metric"] = valid.accepted_metric
    valid["matrix_key"] = valid.metric
    # Choose the earliest accepted publication across sources. SEC accession
    # evidence wins ties. A later comparative SEC filing must never replace an
    # already accepted earlier vendor observation and delay its availability.
    valid["priority"] = np.where(valid.provider.eq("SEC"), 0, 1)
    valid["available_from"] = valid.published_at + pd.Timedelta(days=1)
    cell_keys = ["ticker", "metric", "date"]
    valid = valid.sort_values(cell_keys + ["published_at", "priority", "concept_priority", "input_rank", "row_id"], kind="stable")
    # Same-priority, same earliest publication conflicts are excluded altogether.
    first_pub = valid.groupby(cell_keys).published_at.transform("min")
    preferred = valid.loc[valid.published_at.eq(first_pub)]
    minimum = preferred.groupby(cell_keys).priority.transform("min")
    first = preferred.loc[preferred.priority.eq(minimum)].copy()
    num = first.loc[first.kind.eq("number")].groupby(cell_keys).value.agg(["min", "max"])
    conflict = num.loc[~np.isclose(num["min"], num["max"], rtol=1e-6, atol=1)].index
    reject(pd.Series(pd.MultiIndex.from_frame(data.assign(metric=metrics)[cell_keys]).isin(conflict), index=data.index),
           "CONFLICTING_FIRST_AVAILABLE_SAME_PARAMETER_VALUES")
    valid = valid.loc[reasons.loc[valid.index].eq("")].copy()
    selected = valid.drop_duplicates(cell_keys).copy()
    # No more review buckets: every archived row has exactly one terminal state.
    decisions = data[["row_id", "ticker", "provider", "field", "date", "accepted_metric"]].copy()
    decisions["decision"] = np.where(reasons.eq(""), "ACCEPT", "REJECT")
    decisions["reasons"] = reasons.str.rstrip(";").replace("", "PASSED_DECLARED_DATA_CONTRACT")
    decisions.to_parquet(qa / "all_row_decisions.parquet", index=False)
    rejected = decisions.loc[decisions.decision.eq("REJECT")]
    rejected.groupby(["provider", "field", "reasons"], dropna=False).size().rename("rows").reset_index().to_csv(qa / "rejections_by_field.csv", index=False)
    for flag in ["identity_review", "definition_review", "scope_review", "is_variant", "publication_before_period_end"]:
        valid[flag] = False
        selected[flag] = False
    for frame in [valid, selected]:
        frame["source_semantic_status"] = frame.semantic_status
        frame["semantic_status"] = "ACCEPTED_DECLARED_DEFINITION"
        frame["acceptance_decision"] = "ACCEPT"
    valid["matrix_eligible"] = True
    selected["matrix_eligible"] = True
    valid.to_parquet(staging / "observations_all.parquet", index=False)
    selected.to_parquet(staging / "selected_observations.parquet", index=False)
    for folder in ["Matrices", "Publication_Dates", "Available_From"]:
        (staging / folder).mkdir()
    catalog = []
    for metric, group in selected.groupby("metric"):
        value_col = "date_value" if group.kind.iloc[0] == "date" else "value"
        matrix = group.pivot(index="date", columns="ticker", values=value_col).sort_index().reindex(columns=universe)
        matrix.columns.name, matrix.index.name = "ticker", "date"
        matrix.to_parquet(staging / "Matrices" / (metric + ".parquet"))
        for folder, column in [("Publication_Dates", "published_at"), ("Available_From", "available_from")]:
            aligned = group.pivot(index="date", columns="ticker", values=column).reindex(index=matrix.index, columns=universe)
            aligned.to_parquet(staging / folder / (metric + ".parquet"))
            check = pd.read_parquet(staging / folder / (metric + ".parquet"))
            assert check.index.equals(matrix.index) and check.columns.equals(matrix.columns)
            assert check.notna().equals(matrix.notna())
        check = pd.read_parquet(staging / "Matrices" / (metric + ".parquet"))
        # Check every accepted cell, not a random sample.
        long = check.stack().rename("saved").reset_index()
        comparison = group[["date", "ticker", value_col]].merge(long, on=["date", "ticker"], validate="one_to_one")
        assert len(comparison) == len(group) and comparison[value_col].eq(comparison.saved).all()
        assert matrix.index.is_unique and matrix.index.is_monotonic_increasing and matrix.columns.tolist() == universe
        catalog.append({"metric": metric, "file": "Matrices/" + metric + ".parquet", "variant": False,
                        "kind": group.kind.iloc[0], "unit": "|".join(sorted(group.unit.unique())),
                        "observed_cells": len(group), "tickers_with_values": group.ticker.nunique(),
                        "first_date": str(group.date.min().date()), "last_date": str(group.date.max().date())})
    pd.DataFrame(catalog).to_csv(staging / "dataset_catalog.csv", index=False)
    assert len(decisions) == len(data) and decisions.decision.isin(["ACCEPT", "REJECT"]).all()
    assert len(selected) == sum(c["observed_cells"] for c in catalog)
    assert selected.published_at.notna().all() and selected.published_at.ge(selected.date).all()
    assert not selected.duplicated(cell_keys).any()
    assert digest(source / "observations_all.parquet") == source_hash
    for item in manifest["inputs"]:
        assert digest(ROOT / item["path"]) == item["sha256"], item["path"]
    archive = BASE / "Consolidated_Archive" / ("candidate_snapshot_" + token)
    contract = {"source_snapshot": str(archive if source == TARGET else source), "source_sha256": source_hash,
                "lseg_fields": LSEG_FIELDS, "sec_fields": SEC_FIELDS,
                "selection": "Earliest accepted publication across sources; SEC accession wins publication-date ties; conflicting earliest amounts rejected",
                "timing": "available_from = published_at + 1 calendar day; join to next permitted trading date",
                "missing_expenses": "Remain missing. Never assumed zero.",
                "point_in_time_scope": "SEC filing vintages retained. LSEG Orig requests have vendor-vintage assurance only, not independently certified PIT.",
                "not_book_equity": "Common/parent equity and deferred tax/preferred components remain separate; no automatic FF book-equity formula applied.",
                "accuracy_scope": "All local records screened. Acceptance verifies the declared source, identity evidence, field, dates, units and consistency, not absolute economic truth.",
                "universe_scope": "No new market-price series or price corrections in this company-input finalization."}
    (staging / "acceptance_contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    summary = {"source_rows": len(data), "accepted_source_rows": len(valid), "rejected_source_rows": len(rejected),
               "selected_cells": len(selected), "matrices": len(catalog), "ticker_columns": len(universe),
               "unresolved_rows": 0, "all_saved_cells_verified": True, "source_hashes_unchanged": True,
               "approved_ric_pairs": len(good_rics), "approved_cik_pairs": len(good_ciks),
               "elapsed_seconds": round(time.perf_counter() - started, 2), "inputs": manifest["inputs"]}
    (staging / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    readme = """# Accepted company inputs

Only accepted observations are in Matrices/ and selected_observations.parquet.
There are no pending-review or alternative matrices in this active dataset.
Dates are actual financial period ends (market cap: observation dates), columns
are the 900 historical project tickers. NaN means missing, not zero.

Publication_Dates/ retains publication dates. Available_From/ adds one calendar
day so day-only announcements are not used at that same day's close. Models must
join these dates to the permitted trading calendar, not fill by fiscal end.

observations_all.parquet retains accepted vintages; selected_observations.parquet
selects the earliest accepted publication, with SEC winning publication-date ties. Historical
as-of selection must use the accepted vintage records, not treat one matrix as
an arbitrary-date point-in-time panel.

Each ancillary expense/equity component retains its exact name. Components do
not replace totals. No book-equity, investment or profitability ratio is computed.
Different class tickers may share an issuer; portfolio construction must not
count the same issuer twice. Membership still determines which symbols apply.

acceptance_contract.json defines exact field policy, source-vintage limitations
and the archived candidate snapshot. QA/all_row_decisions.parquet gives ACCEPT
or REJECT for every input row. Rejected and unknown rows are absent from active
matrices; original downloads remain in the audit archive.
"""
    (staging / "README.md").write_text(readme, encoding="utf-8")
    # Validate absolute targets before Windows directory moves; keep rollback.
    assert TARGET.resolve().parent == BASE.resolve() and staging.resolve().parent == BASE.resolve()
    assert archive.resolve().parent.parent == BASE.resolve()
    archive.parent.mkdir(exist_ok=True)
    TARGET.rename(archive)
    try:
        staging.rename(TARGET)
    except BaseException:
        archive.rename(TARGET)
        raise
    REPORT.mkdir(parents=True, exist_ok=True)
    summary_lines = ["# Final company-input acceptance audit", "",
                     f"Source rows: {len(data):,}; accepted source rows: {len(valid):,}; rejected source rows: {len(rejected):,}.",
                     f"Selected cells: {len(selected):,}; matrices: {len(catalog)}; historical ticker columns: {len(universe)}.",
                     "Unresolved decisions: 0. Every saved cell checked against its selected source record.",
                     "No new extraction or model run. Original inputs unchanged; complete candidate snapshot archived.", "",
                     "Acceptance means passed the declared data contract, not a guarantee of source-vendor accuracy or independent PIT certification.",
                     "No stronger claim of complete FF5 eligibility or zero survivorship bias is made."]
    (REPORT / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    for file in ["ric_identity_decisions.csv", "cik_identity_decisions.csv", "rejections_by_field.csv"]:
        (REPORT / file).write_bytes((TARGET / "QA" / file).read_bytes())
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs"}, indent=2), flush=True)


if __name__ == "__main__":
    # Running directly from work/ still needs the project import root for config.
    import sys
    sys.path.insert(0, str(ROOT))
    run()
