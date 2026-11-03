"""Download SEC candidate fundamentals; no portfolio or existing-pipeline changes."""

import argparse
import ast
import gzip
import json
import os
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Fama_French.config import (
    ANNUAL_FORMS, CONCEPTS, FIRST_FISCAL_YEAR, FLOW_METRICS, LAST_FISCAL_YEAR,
    OUTPUT_DIR, PROJECT_ROOT, REQUEST_INTERVAL_SECONDS, UNIVERSE_PATH,
)


def write_json(path, value, compress=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if compress:
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=3) as stream:
            json.dump(value, stream, separators=(",", ":"))
    else:
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temporary, path)


class SecClient:
    def __init__(self, email, root):
        self.root = root
        self.headers = {
            "User-Agent": f"Cross-Sectional Equity Factor Research {email}",
            "Accept-Encoding": "gzip, deflate",
        }
        self.local = threading.local()
        self.lock = threading.Lock()
        self.blocked = threading.Event()
        self.last_request = 0.0
        self.requests = 0
        self.errors = []

    def session(self):
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
            self.local.session.headers.update(self.headers)
        return self.local.session

    def get(self, url, relative_path, text=False):
        path = self.root / relative_path
        if path.exists():
            if text:
                return path.read_text(encoding="utf-8", errors="replace")
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as stream:
                    return json.load(stream)
            return json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(3):
            with self.lock:
                if self.blocked.is_set():
                    raise PermissionError("SEC access denied; acquisition has stopped")
                time.sleep(max(0, REQUEST_INTERVAL_SECONDS - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                self.requests += 1
            try:
                response = self.session().get(url, timeout=(15, 60))
                if response.status_code == 403:
                    self.blocked.set()
                    raise PermissionError("SEC denied access; downloads stopped without bypassing the restriction")
                if response.status_code == 404:
                    return None
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                if text:
                    value = response.text
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_name(path.name + ".tmp")
                    temporary.write_text(value, encoding="utf-8")
                    os.replace(temporary, path)
                else:
                    value = response.json()
                    write_json(path, value, compress=path.suffix == ".gz")
                return value
            except (requests.RequestException, ValueError) as error:
                if attempt == 2:
                    self.errors.append({"url": url, "error": str(error)})
                    raise RuntimeError(f"SEC request failed after retries: {url}: {error}") from error
                time.sleep(2 ** attempt)


def normalize_symbol(value):
    return str(value).strip().upper().replace(".", "-").replace("/", "-")


def normalize_name(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = value.split(", Ordinary Share")[0].split(", Preference Share")[0]
    value = re.sub(r"\bOrd Shs\b.*", "", value, flags=re.I)
    value = re.sub(r"/[^/]+/", " ", value.upper()).replace("&", " AND ")
    words = re.findall(r"[A-Z0-9]+", value)
    endings = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "PLC", "LTD", "LIMITED", "NV", "SA"}
    if words and words[0] == "THE":
        words.pop(0)
    while words and words[-1] in endings:
        words.pop()
    return " ".join(words)


def data_system_settings():
    tree = ast.parse((PROJECT_ROOT / "src/Data_System/config.py").read_text(encoding="utf-8"))
    settings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"YAHOO_TICKER_ALIASES", "YAHOO_REUSED_TICKERS"}:
                    settings[target.id] = ast.literal_eval(node.value)
    return settings


def company_hints():
    hints = {}
    sources = (
        PROJECT_ROOT / "LSEG_Recovery/Audit/frozen_candidates.csv",
        PROJECT_ROOT / "LSEG_Recovery/Remaining_95/Audit/frozen_candidates.csv",
    )
    for path in sources:
        if path.exists():
            frame = pd.read_csv(path, keep_default_na=False)
            for row in frame.itertuples(index=False):
                if row.company:
                    hints.setdefault(row.ticker, set()).add(row.company)
    # The earlier recovery has explicit historical company names for the
    # unresolved securities as well. Read constants without executing its code.
    path = PROJECT_ROOT / "LSEG_Recovery/lseg_recover_remaining_95.py"
    if path.exists():
        for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COMPANY_HINTS" for t in node.targets):
                for ticker, names in ast.literal_eval(node.value).items():
                    hints.setdefault(ticker, set()).update([names] if isinstance(names, str) else names)
    return hints


def resolve_candidates(universe, ticker_data, historical_names):
    current = {}
    for row in ticker_data.values():
        current.setdefault(normalize_symbol(row["ticker"]), []).append(row)
    names_index = {}
    for line in historical_names.splitlines():
        match = re.match(r"^(.*):(\d{1,10}):\s*$", line)
        if match:
            name, cik = match.groups()
            normalized = normalize_name(name)
            if len(normalized) >= 5:
                names_index.setdefault(normalized, {})[str(int(cik))] = name
    hints = company_hints()
    settings = data_system_settings()
    aliases = settings.get("YAHOO_TICKER_ALIASES", {})
    reused = settings.get("YAHOO_REUSED_TICKERS", set()) | {"IR", "FOX", "FOXA", "MCC", "LB"}
    rows = []
    for record in universe.itertuples(index=False):
        ticker = record.ticker
        expected_names = {normalize_name(n) for n in hints.get(ticker, ()) if normalize_name(n)}
        found = {}
        for name in expected_names:
            for cik, company in names_index.get(name, {}).items():
                found[cik] = (company, "historical_company_name_exact")
        for symbol, reason in [(ticker, "current_sec_ticker"), (aliases.get(ticker), "verified_direct_rename")]:
            if not symbol:
                continue
            for entry in current.get(normalize_symbol(symbol), []):
                company = entry["title"]
                # Known old-company names take precedence over a reused symbol.
                if expected_names and normalize_name(company) not in expected_names:
                    continue
                if ticker in reused and not expected_names and reason != "verified_direct_rename":
                    continue
                found.setdefault(str(int(entry["cik_str"])), (company, reason))
        status = "UNRESOLVED" if not found else ("SINGLE_CIK_CANDIDATE" if len(found) == 1 else "MULTIPLE_CIK_CANDIDATES")
        base = {
            "ticker": ticker, "first_membership_date": record.first_membership_date,
            "last_membership_date": record.last_membership_date,
            "historical_company_hints": " | ".join(sorted(hints.get(ticker, ()))),
            "mapping_status": status, "mapping_verified": False,
        }
        if not found:
            rows.append({**base, "cik": "", "sec_company": "", "mapping_basis": "no_unique_identity_source"})
        else:
            for cik, (company, basis) in sorted(found.items()):
                rows.append({**base, "cik": cik.zfill(10), "sec_company": company, "mapping_basis": basis})
    return pd.DataFrame(rows)


def extract_annual_facts(data, first_year=FIRST_FISCAL_YEAR, last_year=LAST_FISCAL_YEAR):
    candidates = []
    for metric, taxonomies in CONCEPTS.items():
        for taxonomy, concepts in taxonomies.items():
            for priority, concept in enumerate(concepts):
                item = data.get("facts", {}).get(taxonomy, {}).get(concept, {})
                for unit, observations in item.get("units", {}).items():
                    if metric != "shares_outstanding" and not re.fullmatch(r"[A-Z]{3}", unit):
                        continue
                    if metric == "shares_outstanding" and unit != "shares":
                        continue
                    for observation in observations:
                        if observation.get("form") not in ANNUAL_FORMS:
                            continue
                        try:
                            end = date.fromisoformat(observation["end"])
                            filed = date.fromisoformat(observation["filed"])
                            start = date.fromisoformat(observation["start"]) if observation.get("start") else None
                        except (KeyError, ValueError, TypeError):
                            continue
                        if not first_year <= end.year <= last_year:
                            continue
                        duration = (end - start).days + 1 if start else None
                        if metric in FLOW_METRICS and (duration is None or not 300 <= duration <= 400):
                            continue
                        candidates.append({
                            "cik": str(data["cik"]).zfill(10), "company": data.get("entityName", ""),
                            "metric": metric, "taxonomy": taxonomy, "concept": concept,
                            "concept_priority": priority, "unit": unit, "value": observation["val"],
                            "period_start": start, "period_end": end, "period_year": end.year,
                            "duration_days": duration, "filed": filed, "form": observation["form"],
                            "accession": observation.get("accn", ""), "filing_fiscal_year": observation.get("fy"),
                            "filing_fiscal_period": observation.get("fp"), "frame": observation.get("frame", ""),
                        })
    if not candidates:
        return pd.DataFrame()
    frame = pd.DataFrame(candidates).drop_duplicates()
    for column in ("period_start", "period_end", "filed"):
        frame[column] = pd.to_datetime(frame[column])
    # Annual flow periods identify financial year ends. Do not confuse every
    # balance-sheet comparison in a 10-K with an independently verified FY end.
    annual_ends = set(frame.loc[frame.metric.isin(FLOW_METRICS), "period_end"])
    frame["annual_period_confirmed"] = frame.period_end.isin(annual_ends)
    return frame


def build_annual_table(facts):
    if facts.empty:
        return pd.DataFrame()
    keys = ["cik", "company", "period_end", "period_year", "filed", "form", "accession", "unit"]
    monetary = facts.loc[facts.metric.ne("shares_outstanding") & facts.annual_period_confirmed].copy()
    if monetary.empty:
        return pd.DataFrame()
    # One filing vintage and currency per row. Never stitch later restatements
    # into an earlier publication date or silently combine different currencies.
    groups = monetary.groupby(keys + ["metric"], dropna=False)
    conflicts = groups.value.nunique().gt(1).rename("conflict").reset_index()
    chosen = monetary.sort_values(["concept_priority", "concept"]).drop_duplicates(keys + ["metric"])
    values = chosen.pivot(index=keys, columns="metric", values="value")
    tags = chosen.pivot(index=keys, columns="metric", values="concept").add_suffix("_source_concept")
    result = values.join(tags).reset_index()
    conflicts = conflicts.loc[conflicts.conflict].groupby(keys, dropna=False).metric.agg("|".join).rename("conflicting_metrics")
    return result.merge(conflicts.reset_index(), on=keys, how="left", validate="one_to_one")


def save_frame(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp" + path.suffix)
    if path.suffix == ".parquet":
        frame.to_parquet(temporary, index=False)
    else:
        frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def write_outputs(root, mapping, status_rows, fact_parts, started, requests_count):
    save_frame(pd.DataFrame(status_rows), root / "download_report.csv")
    save_frame(mapping, root / "ticker_cik_mapping.csv")
    facts = pd.concat(fact_parts, ignore_index=True) if fact_parts else pd.DataFrame()
    annual = build_annual_table(facts)
    save_frame(facts, root / "Processed/annual_facts_all_versions.parquet")
    save_frame(annual, root / "Processed/annual_fundamentals_by_filing.parquet")
    coverage = []
    for ticker, group in mapping.groupby("ticker", sort=False):
        ciks = set(group.cik.dropna().astype(str)) - {""}
        available = facts.loc[facts.cik.isin(ciks)] if not facts.empty else pd.DataFrame()
        row = {
            "ticker": ticker, "mapping_status": group.mapping_status.iloc[0],
            "candidate_ciks": "|".join(sorted(ciks)), "mapping_verified": False,
            "annual_fact_observations": len(available),
            "first_period": str(available.period_end.min().date()) if len(available) else "",
            "last_period": str(available.period_end.max().date()) if len(available) else "",
        }
        for metric in ("total_assets", "equity_parent", "common_equity", "revenue", "cost_of_sales", "sga", "interest_expense"):
            years = sorted(available.loc[available.metric.eq(metric), "period_year"].unique()) if len(available) else []
            row[metric + "_years"] = "|".join(map(str, years))
        coverage.append(row)
    coverage = pd.DataFrame(coverage)
    save_frame(coverage, root / "coverage_report.csv")
    completed = pd.DataFrame(status_rows)
    downloaded = int(completed.status.str.startswith("DOWNLOADED").sum()) if len(completed) else 0
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ticker_count": mapping.ticker.nunique(), "candidate_issuer_count": len(set(mapping.cik) - {""}),
        "candidate_issuers_attempted": len(status_rows),
        "run_complete": len(status_rows) == len(set(mapping.cik) - {""}),
        "issuers_downloaded": downloaded, "annual_fact_observations": len(facts),
        "annual_filing_rows": len(annual), "securities_with_any_selected_facts": int(coverage.annual_fact_observations.gt(0).sum()),
        "mapping_status_counts": mapping.drop_duplicates("ticker").mapping_status.value_counts().to_dict(),
        "requested_fiscal_years": [FIRST_FISCAL_YEAR, LAST_FISCAL_YEAR],
        "http_requests": requests_count, "elapsed_seconds": round(time.monotonic() - started, 2),
        "identity_review_required": True, "complete_fama_french_inputs": False,
    }
    write_json(root / "run_metadata.json", summary)
    lines = ["# SEC EDGAR Fundamentals Extraction", "", f"- Historical securities attempted: **{summary['ticker_count']}**.",
             f"- Candidate issuers downloaded: **{downloaded}**.", f"- Securities with selected annual observations: **{summary['securities_with_any_selected_facts']}**.",
             f"- Annual source observations: **{len(facts):,}**; filing/currency rows: **{len(annual):,}**.",
             "", "## Interpretation", "",
             "Downloads are issuer candidates, not verified historical security matches. Review ticker_cik_mapping.csv and coverage_report.csv before using them.",
             "Annual observations preserve original filing dates, source concepts, units and multiple filing vintages. Missing expenses are not zero. Book equity and FF profitability have not been constructed.",
             "Different candidate concepts may describe different accounting scopes. Conflicts are flagged in the filing table; all values remain in the long source table.",
             "Publication dates govern future availability. A comparative 2008 figure first filed in 2010 is not information available in 2008.",
             "SEC standardized XBRL coverage is limited for early years, custom company tags and some delisted/foreign issuers. Missing fields do not imply the company did not report them.",
             "Historical market capitalization is a separate outstanding input. Share facts alone are not a monthly shares series.",
             "", "## Files", "", "- `Raw/Reference/`: official ticker and historical-name indexes.",
             "- `Raw/Submissions/`: issuer metadata; `Raw/CompanyFacts/`: complete original company-facts JSON, gzip-compressed.",
             "- `Processed/annual_facts_all_versions.parquet`: selected annual source observations and filing vintages.",
             "- `Processed/annual_fundamentals_by_filing.parquet`: candidate values within one filing vintage and currency.",
             "- `ticker_cik_mapping.csv`, `coverage_report.csv`, `download_report.csv`, `run_metadata.json`.",
             "", "Source: https://www.sec.gov/search-filings/edgar-application-programming-interfaces", ""]
    (root / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def download_issuer(client, cik, related):
    metadata_error = ""
    try:
        submissions = client.get(f"https://data.sec.gov/submissions/CIK{cik}.json", Path(f"Raw/Submissions/CIK{cik}.json.gz"))
    except RuntimeError as error:
        submissions, metadata_error = None, str(error)
    try:
        data = client.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", Path(f"Raw/CompanyFacts/CIK{cik}.json.gz"))
        if data and int(data["cik"]) != int(cik):
            raise ValueError("Response CIK does not match requested issuer")
        frame = extract_annual_facts(data) if data else pd.DataFrame()
        status = "NO_STANDARDIZED_COMPANYFACTS" if data is None else ("DOWNLOADED" if len(frame) else "DOWNLOADED_NO_SELECTED_ANNUAL_FACTS")
        row = {"cik": cik, "tickers": related, "company": (data or {}).get("entityName", (submissions or {}).get("name", "")),
               "status": status, "submissions_available": submissions is not None,
               "annual_fact_observations": len(frame), "mapping_verified": False, "error": metadata_error}
        return row, frame
    except (RuntimeError, ValueError, KeyError, TypeError) as error:
        return {"cik": cik, "tickers": related, "status": "REQUEST_OR_EXTRACTION_ERROR", "error": str(error),
                "submissions_available": submissions is not None, "annual_fact_observations": 0,
                "mapping_verified": False}, pd.DataFrame()


def run(email=None, limit=None, workers=4):
    started = time.monotonic()
    root = OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    email = email or os.environ.get("SEC_CONTACT_EMAIL")
    contact = root / "sec_contact.txt"
    if not email and contact.exists():
        email = contact.read_text().strip()
    if not email or "@" not in email:
        raise ValueError("Provide SEC_CONTACT_EMAIL, --email, or Data/Fama and french/sec_contact.txt")
    client = SecClient(email, root)
    print("Loading SEC reference files (local copies are reused)...", flush=True)
    tickers = client.get("https://www.sec.gov/files/company_tickers.json", Path("Raw/Reference/company_tickers.json"))
    names = client.get("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt", Path("Raw/Reference/cik_lookup.txt"), text=True)
    if tickers is None or names is None:
        raise RuntimeError("SEC identity reference files could not be downloaded")
    universe = pd.read_csv(UNIVERSE_PATH, keep_default_na=False)
    print(f"Resolving issuer candidates for {len(universe)} historical securities...", flush=True)
    mapping = resolve_candidates(universe, tickers, names)
    save_frame(mapping, root / "ticker_cik_mapping.csv")
    ciks = sorted(set(mapping.cik) - {""})
    if limit is not None:
        ciks = ciks[:limit]
    print(f"Historical securities: {len(universe)} | candidate issuers: {len(ciks)}", flush=True)
    statuses, parts = [], []
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
            futures = {
                pool.submit(download_issuer, client, cik, "|".join(mapping.loc[mapping.cik.eq(cik), "ticker"])): cik
                for cik in ciks
            }
            for number, future in enumerate(as_completed(futures), 1):
                row, frame = future.result()
                if len(frame):
                    parts.append(frame)
                statuses.append(row)
                print(f"[{number}/{len(ciks)}] {row['tickers']} -> {row['cik']}: {row['status']} ({len(frame):,} facts)", flush=True)
                if number % 10 == 0:
                    save_frame(pd.DataFrame(statuses), root / "download_report.csv")
    finally:
        summary = write_outputs(root, mapping, statuses, parts, started, client.requests)
        save_frame(pd.DataFrame(client.errors), root / "request_errors.csv")
        print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Contact address used only in the SEC request header")
    parser.add_argument("--limit", type=int, help="Limit candidate issuers for a short acquisition check")
    parser.add_argument("--workers", type=int, default=4, help="Up to four workers, sharing a global sub-3-requests/second limit")
    args = parser.parse_args()
    run(email=args.email, limit=args.limit, workers=args.workers)
