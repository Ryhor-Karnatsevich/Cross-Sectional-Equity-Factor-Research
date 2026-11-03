"""Target missing annual inputs in original SEC filings, including custom XBRL."""

import argparse
import gzip
import json
import re
import sys
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Fama_French.config import ANNUAL_FORMS, CONCEPTS, FIRST_FISCAL_YEAR, LAST_FISCAL_YEAR, OUTPUT_DIR, PROJECT_ROOT
from Fama_French.refine_sec import SUPPLEMENTAL_CONCEPTS, recover_accounting_identities, required_period_coverage
from Fama_French.sec_edgar import SecClient, build_annual_table, save_frame, write_json


FIELDS = ("revenue", "cost_of_sales", "sga", "interest_expense", "equity_parent", "total_assets")
PARSE_VERSION = 2
FLOW_FIELDS = {"revenue", "cost_of_sales", "sga", "interest_expense"} | set(SUPPLEMENTAL_CONCEPTS)
XLINK = "{http://www.w3.org/1999/xlink}"
SOURCE_CONCEPTS = {
    (taxonomy, concept): (metric, priority)
    for metric, taxonomies in {**CONCEPTS, **SUPPLEMENTAL_CONCEPTS}.items()
    for taxonomy, concepts in taxonomies.items()
    for priority, concept in enumerate(concepts)
}
CUSTOM_LABELS = {
    "revenue": {"revenue", "revenues", "total revenues", "total revenue", "net revenues", "net revenue", "net sales", "sales"},
    "cost_of_sales": {"cost of revenue", "cost of revenues", "cost of sales", "cost of goods sold", "cost of goods and services sold"},
    "sga": {"selling general and administrative", "selling general and administrative expense", "selling general and administrative expenses"},
    "interest_expense": {"interest expense", "interest expenses", "total interest expense"},
    "equity_parent": {"stockholders equity", "shareholders equity", "total stockholders equity", "total shareholders equity"},
    "total_assets": {"assets", "total assets"},
    "gross_profit": {"gross profit"},
    "selling_marketing": {"selling and marketing", "selling and marketing expense", "selling and marketing expenses", "sales and marketing"},
    "general_administrative": {"general and administrative", "general and administrative expense", "general and administrative expenses"},
}


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def normalized_label(text):
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("&", "and"))


def label_map(xml):
    labels = {}
    if not xml:
        return labels
    root = ET.fromstring(xml)
    for link in root.iter():
        if local_name(link.tag) != "labelLink":
            continue
        locations, resources = {}, {}
        for child in link:
            kind = local_name(child.tag)
            if kind == "loc":
                locations[child.get(XLINK + "label")] = child.get(XLINK + "href", "").split("#")[-1].split("_", 1)[-1]
            elif kind == "label" and (not child.get(XLINK + "role") or child.get(XLINK + "role").endswith("/label")):
                resources[child.get(XLINK + "label")] = " ".join(child.itertext()).strip()
        for child in link:
            if local_name(child.tag) == "labelArc":
                concept, text = locations.get(child.get(XLINK + "from")), resources.get(child.get(XLINK + "to"))
                if concept and text:
                    labels.setdefault(concept, set()).add(text)
    return labels


def face_concepts(xml):
    faces = set()
    if not xml:
        return faces
    for link in ET.fromstring(xml).iter():
        if local_name(link.tag) != "presentationLink":
            continue
        role = link.get(XLINK + "role", "")
        if not re.search(r"Income|Operations|Earnings|ProfitAndLoss|BalanceSheet|FinancialPosition", role, re.I):
            continue
        if re.search(r"Parenthetical|Segment|Schedule|Detail", role, re.I):
            continue
        for child in link:
            if local_name(child.tag) == "loc":
                faces.add(child.get(XLINK + "href", "").split("#")[-1].split("_", 1)[-1])
    return faces


def parse_instance(xml, labels, faces, filing):
    root = ET.fromstring(xml)
    contexts, units = {}, {}
    for element in root:
        kind = local_name(element.tag)
        if kind == "context":
            members = {local_name(e.tag) for e in element.iter()}
            if members & {"explicitMember", "typedMember"}:
                continue
            values = {local_name(e.tag): (e.text or "").strip() for e in element.iter()}
            if not values.get("identifier", "").isdigit() or int(values["identifier"]) != int(filing["cik"]):
                continue
            contexts[element.get("id")] = values
        elif kind == "unit":
            measures = [e.text for e in element.iter() if local_name(e.tag) == "measure"]
            if len(measures) == 1:
                units[element.get("id")] = measures[0].split(":")[-1]
    rows = []
    for element in root:
        context = contexts.get(element.get("contextRef"))
        unit = units.get(element.get("unitRef"))
        if not context or not unit or not (unit == "shares" or re.fullmatch(r"[A-Z]{3}", unit)):
            continue
        concept = local_name(element.tag)
        namespace = element.tag.partition("}")[0].lstrip("{")
        taxonomy = "us-gaap" if "us-gaap" in namespace else ("ifrs-full" if "ifrs" in namespace else ("dei" if "/dei/" in namespace else "custom"))
        match = SOURCE_CONCEPTS.get((taxonomy, concept))
        label = " | ".join(sorted(labels.get(concept, ())))
        basis = "standard_concept"
        if match is None and taxonomy == "custom" and concept in faces:
            matches = {metric for metric, names in CUSTOM_LABELS.items()
                       if any(normalized_label(text) in {normalized_label(n) for n in names} for text in labels.get(concept, ()))}
            if len(matches) == 1:
                match, basis = (matches.pop(), 50), "exact_custom_face_label"
            elif not matches and any(re.search(r"expense|cost|revenue|sales|equity|assets", text, re.I) for text in labels.get(concept, ())):
                match, basis = ("custom_scope_review", 1000), "custom_scope_review"
        if match is None:
            continue
        metric, priority = match
        if (metric == "shares_outstanding") != (unit == "shares"):
            continue
        try:
            value = float((element.text or "").strip())
            end = date.fromisoformat(context.get("endDate", context.get("instant", "")))
            start = date.fromisoformat(context["startDate"]) if context.get("startDate") else None
        except (ValueError, TypeError):
            continue
        duration = (end - start).days + 1 if start else None
        if not np.isfinite(value) or not FIRST_FISCAL_YEAR <= end.year <= LAST_FISCAL_YEAR:
            continue
        if metric in FLOW_FIELDS and (duration is None or not 300 <= duration <= 400):
            continue
        if metric == "custom_scope_review" and duration is not None and not 300 <= duration <= 400:
            continue
        rows.append({"cik": filing["cik"], "company": filing["company"], "metric": metric,
                     "taxonomy": taxonomy, "concept": concept, "concept_priority": priority,
                     "unit": unit, "value": value, "period_start": start, "period_end": end,
                     "period_year": end.year, "duration_days": duration, "filed": filing["filed"],
                     "form": filing["form"], "accession": filing["accession"], "filing_fiscal_year": filing["period_year"],
                     "filing_fiscal_period": "FY", "frame": "", "source_label": label,
                     "source_url": filing["instance_url"], "extraction_basis": basis,
                     "custom_label_review_required": basis != "standard_concept"})
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).drop_duplicates()
    for column in ("period_start", "period_end", "filed"):
        frame[column] = pd.to_datetime(frame[column])
    annual_ends = set(frame.loc[frame.metric.isin(FLOW_FIELDS), "period_end"])
    frame["annual_period_confirmed"] = frame.period_end.isin(annual_ends)
    return recover_accounting_identities(frame)


def build_requests(baseline, mapping, membership):
    links = mapping.loc[mapping.mapping_status.eq("SINGLE_CIK_CANDIDATE")].set_index("ticker")
    counts = membership.loc["2010-01-01":].groupby(
        membership.loc["2010-01-01":].index.year - (membership.loc["2010-01-01":].index.month < 7).astype(int)
    ).sum()
    rows = []
    for year, weights in counts.iterrows():
        known = baseline.loc[baseline.unit.eq("USD") & baseline.period_year.eq(year - 1) & baseline.filed.le(pd.Timestamp(year, 6, 30))]
        available = {field: set(known.loc[known[field].notna(), "cik"]) for field in FIELDS}
        for ticker in weights.index[weights.gt(0)]:
            if ticker not in links.index:
                continue
            item = links.loc[ticker]
            missing = [field for field in FIELDS if item.cik not in available[field]]
            if missing:
                rows.append({"ticker": ticker, "cik": item.cik, "company": item.sec_company,
                             "period_year": int(year - 1), "formation_date": f"{year}-06-30",
                             "missing_fields": "|".join(missing), "member_days": int(weights[ticker])})
    columns = ["ticker", "cik", "company", "period_year", "formation_date", "missing_fields", "member_days"]
    return pd.DataFrame(rows, columns=columns).sort_values(["period_year", "member_days", "ticker"], ascending=[False, False, True])


def choose_filing(request, raw_facts, submissions):
    recent = submissions.get("filings", {}).get("recent", {})
    candidates = []
    for i, form in enumerate(recent.get("form", [])):
        report_date = recent.get("reportDate", [""] * len(recent["form"]))[i]
        filed = recent["filingDate"][i]
        if form in ANNUAL_FORMS and report_date[:4] == str(request.period_year) and filed <= request.formation_date:
            candidates.append({"accession": recent["accessionNumber"][i], "filed": filed, "form": form})
    if not candidates:
        known = raw_facts.loc[raw_facts.cik.eq(request.cik) & raw_facts.period_year.eq(request.period_year) & raw_facts.filed.le(request.formation_date)]
        for row in known.sort_values("filed").drop_duplicates("accession").itertuples():
            candidates.append({"accession": row.accession, "filed": row.filed.date().isoformat(), "form": row.form})
    return min(candidates, key=lambda item: item["filed"]) if candidates else None


class FilingClient(SecClient):
    """Avoid concurrent writers when comparative years share one filing."""
    def __init__(self, email, root):
        super().__init__(email, root)
        self.cache_locks = {}
        self.cache_guard = threading.Lock()

    def get(self, url, relative_path, text=False):
        with self.cache_guard:
            lock = self.cache_locks.setdefault(str(relative_path), threading.Lock())
        with lock:
            return super().get(url, relative_path, text=text)


def download_filing(client, request, raw_facts):
    local = OUTPUT_DIR / f"Online/Parsed/{request.cik}_{request.period_year}"
    metadata_path, data_path = local.with_suffix(".json"), local.with_suffix(".parquet")
    if metadata_path.exists() and data_path.exists():
        cached = json.loads(metadata_path.read_text(encoding="utf-8"))
        if cached.get("parse_version") == PARSE_VERSION:
            return {**cached["result"], **request._asdict()}, pd.read_parquet(data_path)
    result, frame = fetch_filing(client, request, raw_facts)
    if result["status"] == "PARSED":
        save_frame(frame, data_path)
        write_json(metadata_path, {"parse_version": PARSE_VERSION, "result": result})
    return result, frame


def fetch_filing(client, request, raw_facts):
    row = request._asdict()
    try:
        profile_path = OUTPUT_DIR / f"Raw/Submissions/CIK{request.cik}.json.gz"
        if not profile_path.exists():
            return {**row, "status": "NO_CACHED_ISSUER_PROFILE"}, pd.DataFrame()
        with gzip.open(profile_path, "rt", encoding="utf-8") as stream:
            profile = json.load(stream)
        selected = choose_filing(request, raw_facts, profile)
        if selected is None:
            # Recent submissions omit older annual reports. Request only the
            # historical metadata chunks intersecting this formation window.
            for chunk in profile.get("filings", {}).get("files", []):
                if chunk.get("filingFrom", "9999") > request.formation_date or chunk.get("filingTo", "") < f"{request.period_year}-01-01":
                    continue
                name = chunk.get("name", "")
                if not name or Path(name).name != name:
                    continue
                history = client.get(
                    "https://data.sec.gov/submissions/" + quote(name),
                    Path("Online/Raw/SubmissionHistory") / name,
                )
                if history:
                    selected = choose_filing(request, raw_facts, {"filings": {"recent": history}})
                if selected is not None:
                    break
        if selected is None:
            return {**row, "status": "NO_KNOWN_TIMELY_ANNUAL_FILING"}, pd.DataFrame()
        accession = selected["accession"]
        base = f"https://www.sec.gov/Archives/edgar/data/{int(request.cik)}/{accession.replace('-', '')}/"
        local = Path(f"Online/Raw/{request.cik}/{accession}")
        index = client.get(base + "index.json", local / "index.json")
        if index is None:
            return {**row, **selected, "status": "NO_FILING_DIRECTORY"}, pd.DataFrame()
        files = [item["name"] for item in index["directory"]["item"] if Path(item["name"]).name == item["name"]]
        instances = [name for name in files if name.endswith("_htm.xml")]
        if not instances:
            instances = [name for name in files if name.endswith(".xml") and not re.search(r"_(cal|def|lab|pre)\.xml$|FilingSummary|MetaLinks|Financial_Report", name, re.I)]
        if not instances:
            return {**row, **selected, "status": "NO_XBRL_INSTANCE"}, pd.DataFrame()
        instance = client.get(base + quote(instances[0]), local / instances[0], text=True)
        labels_file = next((name for name in files if name.endswith("_lab.xml")), None)
        presentation_file = next((name for name in files if name.endswith("_pre.xml")), None)
        labels_xml = client.get(base + quote(labels_file), local / labels_file, text=True) if labels_file else None
        presentation_xml = client.get(base + quote(presentation_file), local / presentation_file, text=True) if presentation_file else None
        filing = {**row, **selected, "instance_url": base + quote(instances[0])}
        frame = parse_instance(instance, label_map(labels_xml), face_concepts(presentation_xml), filing)
        return {**row, **selected, "status": "PARSED", "source_url": filing["instance_url"],
                "source_observations": len(frame), "custom_label_observations": int(frame.custom_label_review_required.fillna(False).sum()) if len(frame) else 0}, frame
    except (ValueError, RuntimeError, ET.ParseError, KeyError, TypeError) as error:
        return {**row, "status": "EXTRACTION_ERROR", "error": str(error)}, pd.DataFrame()


def run(limit=None, tickers=None, years=None):
    root = OUTPUT_DIR / "Online"
    root.mkdir(parents=True, exist_ok=True)
    baseline = pd.read_parquet(OUTPUT_DIR / "Refined/annual_fundamentals_by_filing.parquet")
    raw_facts = pd.read_parquet(OUTPUT_DIR / "Refined/annual_facts_all_versions.parquet")
    mapping = pd.read_csv(OUTPUT_DIR / "ticker_cik_mapping.csv", dtype={"cik": str}, keep_default_na=False)
    membership = pd.read_parquet(PROJECT_ROOT / "Data/Data_System/Processed/membership.parquet").astype(bool)
    requests = build_requests(baseline, mapping, membership)
    save_frame(requests, root / "missing_input_requests.csv")
    selected = requests.copy()
    if tickers:
        selected = selected.loc[selected.ticker.isin(tickers)]
    if years:
        selected = selected.loc[selected.period_year.isin(years)]
    selected = selected.drop_duplicates(["cik", "period_year"])
    if limit is not None:
        selected = selected.head(limit)
    save_frame(selected, root / "requests_this_run.csv")
    client = FilingClient((OUTPUT_DIR / "sec_contact.txt").read_text().strip(), OUTPUT_DIR)
    observations_path = root / "filing_observations.parquet"
    previous = pd.read_parquet(observations_path) if observations_path.exists() else pd.DataFrame()
    facts_by_cik = {cik: frame for cik, frame in raw_facts.groupby("cik", sort=False)}
    print(f"Original SEC filings: {len(selected)} targeted company-years; {len(requests)} total gap requests", flush=True)
    rows, parts = [], []
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(download_filing, client, row, facts_by_cik.get(row.cik, raw_facts.iloc[0:0])) for row in selected.itertuples(index=False)]
            for number, future in enumerate(as_completed(futures), 1):
                row, frame = future.result()
                rows.append(row)
                if len(frame):
                    parts.append(frame)
                print(f"[{number}/{len(selected)}] {row['ticker']} {row['period_year']}: {row['status']} ({len(frame)} observations)", flush=True)
                if number % 10 == 0:
                    save_frame(pd.DataFrame(rows), root / "download_report.csv")
    finally:
        additions = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        updated = {(row["cik"], row["accession"]) for row in rows if row["status"] == "PARSED"}
        if len(previous):
            keep = ~pd.MultiIndex.from_frame(previous[["cik", "accession"]]).isin(updated)
            additions = pd.concat([previous.loc[keep], additions], ignore_index=True).drop_duplicates()
        save_frame(additions, observations_path)
        save_frame(pd.DataFrame(rows), root / "download_report.csv")
        review = additions.loc[additions.metric.eq("custom_scope_review")] if len(additions) else additions
        save_frame(review, root / "custom_concept_review.csv")
        usable = additions.loc[additions.metric.ne("custom_scope_review")] if len(additions) else additions
        combined = pd.concat([raw_facts, usable], ignore_index=True) if len(usable) else raw_facts
        annual = build_annual_table(combined)
        save_frame(annual, root / "annual_fundamentals_by_filing.parquet")
        coverage = pd.concat([required_period_coverage(baseline, mapping, membership, "before_online"),
                              required_period_coverage(annual, mapping, membership, "after_online")], ignore_index=True)
        save_frame(coverage, root / "coverage_by_required_period.csv")
        summary = {"gap_requests": len(requests), "selected_requests": len(selected), "processed_requests": len(rows),
                   "http_requests": client.requests, "filing_observations": len(additions),
                   "custom_scope_review_observations": len(review),
                   "entire_gap_list_processed": len(rows) == len(requests),
                   "status_counts": pd.DataFrame(rows).status.value_counts().to_dict() if rows else {},
                   "custom_label_review_required": True, "complete_fama_french_inputs": False}
        write_json(root / "run_metadata.json", summary)
        table = coverage.loc[coverage.research_start.eq("2010-01-01")].pivot(index="metric", columns="stage", values="coverage_pct")
        lines = ["# Original SEC Filing Extraction", "", f"Targeted requests: **{len(selected)}**; processed: **{len(rows)}**; source observations: **{len(additions):,}**.",
                 "", "Original raw, first-pass and offline-refined datasets are unchanged. Newly downloaded filing documents are cached under Online/Raw.",
                 "", "## Coverage for 2010–2026", "", "| Input | Before online | After online |", "| --- | ---: | ---: |"]
        for metric, values in table.iterrows():
            lines.append(f"| {metric} | {values.before_online:.2f}% | {values.after_online:.2f}% |")
        lines += ["", "Only non-dimensional contexts matching the issuer are extracted. Annual flow periods must span 300–400 days. Filing dates and original source URLs are retained. Custom labels require an exact mapping on a primary statement presentation role; mapped custom concepts remain review candidates.",
                  "", "No missing field is assumed zero. Broad operating costs, net interest and other differently scoped totals are not silently substituted for specific expenses. Coverage measures candidate input availability, not verified Fama-French model readiness.", ""]
        (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum company-years for a bounded online test; default processes all gaps")
    parser.add_argument("--all", action="store_true", help="Process every selected gap; can take substantially longer")
    parser.add_argument("--tickers", help="Optional comma-separated historical tickers")
    parser.add_argument("--years", help="Optional comma-separated fiscal period-end years")
    args = parser.parse_args()
    run(limit=None if args.all else args.limit,
        tickers=args.tickers.split(",") if args.tickers else None,
        years=[int(year) for year in args.years.split(",")] if args.years else None)
