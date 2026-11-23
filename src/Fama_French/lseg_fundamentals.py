"""Standalone LSEG fundamentals feasibility test and resumable downloader.

Install on the university PC: pip install lseg-data pandas
Open LSEG Workspace and sign in, then run THIS file. No other project code,
mapping file or SEC downloads are needed for the default 20-company test.

Default: annual accounting periods 2006-2025 and monthly market cap from
December 2007 through August 2026. This is intentionally a bounded pilot.
The original date range is retained so early and recent coverage can be compared.

Outputs: Data/Fama and french/LSEG when inside this project; otherwise
lseg_fundamentals_output beside the copied script. report.md is the main result.
SQLite stores raw responses and checkpoints; successful calls are reused.

Optional commands, using this SAME file:
  python lseg_fundamentals.py --limit 3
  python lseg_fundamentals.py --input mapping.csv --all
  python lseg_fundamentals.py --refresh
Input CSV: ticker,ric; optional company,isin,first_membership_date,last_membership_date.
The existing project universe.csv also works for its non-empty lseg_ric entries.
--all never discovers/guesses identifiers or expands beyond the explicit input.

Candidate extraction only: no missing-to-zero fill, no current shares multiplied
by historical prices, no acquirer substitution, and no automatic dataset merge.
An original-report request is NOT a certified point-in-time database export.
Company market cap aggregates share classes; do not count it twice later.

Official API and field references:
https://cdn.refinitiv.com/public/lseg-lib-python-doc/2.0.0.2/book/en/sections/content-layer/fundamental-reference/fundamental-and-reference-definition.html
https://community.developers.lseg.com/discussion/83314/downloading-data-in-a-bulk-some-calendar-years-cy-are-not-recognized-in-some-years-for-some-va
https://community.developers.lseg.com/discussion/27031/python-datetime-date-on-field-tr-bssourcedate-or-tr-bsoriginalannouncementdate-fundamentals-data
https://community.developers.lseg.com/discussion/34898/how-to-get-history-data-of-stock-market-value-data/p1
"""

import argparse
import hashlib
import inspect
import io
import json
import math
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# -------------------------
# SETTINGS: running normally downloads ONLY this 20-company pilot.
FIRST_FISCAL_YEAR = 2006
LAST_FISCAL_YEAR = 2025
MARKET_START = "2007-12-01"
MARKET_END = "2026-08-18"
DEFAULT_LIMIT = 20
SCRIPT_VERSION = "2026-11-16.2"
PAUSE_SECONDS = 0.35
HEARTBEAT_SECONDS = 10
MAX_ATTEMPTS = 2
CACHE_VERSION = 2

# Existing project price-recovery RICs are preserved, including delisting suffixes.
# These remain identity candidates. Embedded ISINs help reveal ticker reuse.
PILOT = [
    ("AAPL", "AAPL.O", "Apple Inc", "US0378331005"),
    ("MSFT", "MSFT.O", "Microsoft Corp", "US5949181045"),
    ("AMZN", "AMZN.O", "Amazon.com Inc", "US0231351067"),
    ("JPM", "JPM.N", "JPMorgan Chase & Co", "US46625H1005"),
    ("BAC", "BAC.N", "Bank of America Corp", "US0605051046"),
    ("GS", "GS.N", "Goldman Sachs Group Inc", "US38141G1040"),
    ("XOM", "XOM.N", "Exxon Mobil Corp", "US30231G1022"),
    ("CAT", "CAT.N", "Caterpillar Inc", "US1491231015"),
    ("HIG", "HIG.N", "Hartford Financial Services Group Inc", "US4165151048"),
    ("NEE", "NEE.N", "NextEra Energy Inc", "US65339F1012"),
    ("AVB", "AVB^H26", "AvalonBay Communities Inc", "US0534841012"),
    ("EQR", "VMRK.K", "Equity Residential historical security", "US29476L1070"),
    ("ATVI", "ATVI.O^J23", "Activision Blizzard Inc", "US00507V1098"),
    ("CELG", "CELG.O^K19", "Celgene Corp", "US1510201049"),
    ("TWTR", "TWTR.K^J22", "Twitter Inc", "US90184L1026"),
    ("EMC", "EMC^I16", "EMC Corp", "US2686481027"),
    ("AABA", "AABA.O^J19", "Altaba Inc / historical Yahoo", "US0213461017"),
    ("MER", "MER.N^A09", "Merrill Lynch & Co Inc", "US5901881087"),
    ("BSC", "BSC.N^F08", "Bear Stearns Companies Inc", "US0739021089"),
    ("WBA", "WBA.O^H25", "Walgreens Boots Alliance Inc", "US9314271084"),
]

# One metric per request, with its OWN period-end date. Different equity
# definitions are separate metrics, never interchangeable automatic fallbacks.
ANNUAL_FIELDS = {
    "total_assets": "TR.TotalAssetsReported",
    "revenue": "TR.TotalRevenue",
    "cost_of_sales_provider": "TR.CostofRevenueTotal",
    "sga": "TR.SgaExpenseTotal",
    "interest_expense_provider": "TR.InterestExpense",
    "total_equity_provider": "TR.TotalEquity",
    "common_shareholders_equity_provider": "TR.F.ShHoldEqCom",
    "minority_interest_provider": "TR.F.MinIntr",
    "income_original_announcement": "TR.ISOriginalAnnouncementDate",
    "balance_original_announcement": "TR.BSOriginalAnnouncementDate",
}
CORE_METRICS = set(ANNUAL_FIELDS) - {
    "minority_interest_provider", "income_original_announcement", "balance_original_announcement"
}
OBSERVATION_COLUMNS = [
    "ticker", "ric", "expected_company", "expected_isin", "metric", "provider_field",
    "period_end", "provider_date", "numeric_value", "date_value", "raw_value",
    "requested_currency", "requested_scale", "requested_reporting_state",
    "period_date_kind", "source_row", "request_key", "provider_errors",
]


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def default_output():
    for parent in Path(__file__).resolve().parents:
        if (parent / "src/Data_System/config.py").exists():
            return parent / "Data/Fama and french/LSEG"
    return Path(__file__).resolve().parent / "lseg_fundamentals_output"


def save_text(path, text):
    """A locked human-readable report must not terminate extraction."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(text, encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8")
    try:
        os.replace(temporary, path)
        return path
    except PermissionError:
        fallback = path.with_name(path.stem + "_latest_" + uuid.uuid4().hex[:8] + path.suffix)
        os.replace(temporary, fallback)
        print(f"  WARNING: {path.name} is locked; saved {fallback.name} instead.", flush=True)
        return fallback


def load_companies(path, limit, all_companies):
    if path:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frame.columns = [str(c).strip().lower() for c in frame.columns]
        if "ric" not in frame and "lseg_ric" in frame:
            frame["ric"] = frame["lseg_ric"]
        if "isin" not in frame and "lseg_isin" in frame:
            frame["isin"] = frame["lseg_isin"]
        if not {"ticker", "ric"}.issubset(frame.columns):
            raise ValueError("Input CSV needs ticker and ric (or lseg_ric) columns.")
        for col in ("ticker", "ric"):
            frame[col] = frame[col].str.strip()
        missing = frame.ticker.eq("") | frame.ric.eq("")
        if missing.any():
            print(f"Input: {int(missing.sum())} rows have no ticker/RIC and cannot be requested.", flush=True)
        frame = frame.loc[~missing].copy()
    else:
        if all_companies:
            raise ValueError("--all requires --input mapping.csv; default is the explicit pilot.")
        frame = pd.DataFrame(PILOT, columns=["ticker", "ric", "company", "isin"])
    for col in ("company", "isin"):
        if col not in frame:
            frame[col] = ""
    frame = frame.drop_duplicates(["ticker", "ric"])
    if not all_companies:
        frame = frame.head(limit)
    if frame.empty:
        raise ValueError("No ticker/RIC pairs selected.")
    return frame.to_dict("records")


class StopExtraction(RuntimeError):
    pass


def create_definition(api, ric, fields, parameters):
    """Use the actual installed SDK constructor, not a different version's docs."""
    factory = api.content.fundamental_and_reference.Definition
    accepted = inspect.signature(factory).parameters
    kwargs = {"universe": [ric], "fields": fields, "parameters": parameters}
    if "header_type" in accepted:
        # Public API in lseg-data 2.1.1 (HeaderType is exported by lseg.data).
        kwargs["header_type"] = api.HeaderType.NAME
    elif "use_field_names_in_headers" in accepted:
        # Older SDK releases used a boolean instead of the HeaderType enum.
        kwargs["use_field_names_in_headers"] = True
    else:
        raise StopExtraction(
            "Unsupported LSEG constructor: cannot request unambiguous field-code headers. "
            f"Installed SDK: {getattr(api, '__version__', 'unknown')}; signature: {inspect.signature(factory)}"
        )
    return factory(**kwargs)


def canonicalize_columns(frame, requested):
    """Resolve field-code spelling/parameters; never infer data columns by order."""
    def key(value):
        value = str(value).split("|", 1)[0]
        value = re.sub(r"\([^()]*\)", "", value)
        value = re.sub(r"\s+", "", value).casefold()
        return value[:-6] if value.endswith(".value") else value
    targets = {key(code): code for code in requested}
    frame = frame.copy()
    frame.attrs["original_columns"] = [str(col) for col in frame.columns]
    frame.columns = [targets.get(key(col), str(col)) for col in frame.columns]
    return frame


class Downloader:
    def __init__(self, api, output, refresh=False):
        self.api, self.output, self.refresh = api, output, refresh
        output.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(output / "extraction.sqlite", timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS responses "
                        "(key TEXT PRIMARY KEY, request TEXT, table_json TEXT, errors TEXT, fetched TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts "
                        "(id INTEGER PRIMARY KEY, request_key TEXT, started TEXT, seconds REAL, status TEXT, detail TEXT)")
        self.started = time.perf_counter()
        self.calls = self.hits = 0
        self.local_errors = 0
        self.network_seconds = 0.0
        self.last_call = 0.0
        self.completed = 0
        self.total = 0

    def close(self):
        self.db.close()

    def request(self, ric, fields, parameters, label):
        spec = {"cache_version": CACHE_VERSION, "ric": ric, "fields": fields, "parameters": parameters}
        encoded = json.dumps(spec, sort_keys=True)
        key = hashlib.sha256(encoded.encode()).hexdigest()
        cached = self.db.execute("SELECT table_json, errors FROM responses WHERE key=?", (key,)).fetchone()
        if cached and not self.refresh:
            try:
                frame = pd.read_json(io.StringIO(cached[0]), orient="split", convert_dates=False)
                frame = canonicalize_columns(frame, fields)
                self.hits += 1
                return frame, json.loads(cached[1]), key, True
            except (ValueError, TypeError):
                pass
        for attempt in range(1, MAX_ATTEMPTS + 1):
            time.sleep(max(0, PAUSE_SECONDS - (time.perf_counter() - self.last_call)))
            self.last_call = begin = time.perf_counter()
            started = datetime.now(timezone.utc).isoformat()
            stopped = threading.Event()

            def heartbeat():
                while not stopped.wait(HEARTBEAT_SECONDS):
                    print(f"  Waiting: {label}; request {duration(time.perf_counter()-begin)}; "
                          f"total elapsed {duration(time.perf_counter()-self.started)}", flush=True)

            thread = threading.Thread(target=heartbeat, daemon=True)
            thread.start()
            submitted = False
            try:
                definition = create_definition(self.api, ric, fields, parameters)
                # Counts SDK get_data invocations, not physical HTTP requests:
                # the SDK can issue several HTTP calls for one response.
                self.calls += 1
                submitted = True
                response = definition.get_data()
                raw = getattr(getattr(response, "data", None), "df", None)
                source_frame = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
                frame = canonicalize_columns(source_frame, fields)
                errors = getattr(response, "errors", None)
                errors = json.loads(json.dumps(errors, default=str)) if errors else []
                elapsed = time.perf_counter() - begin
                self.network_seconds += elapsed
                if errors:
                    self.check_fatal(str(errors))
                # Error-bearing replies remain raw evidence, not successful cache hits.
                self.db.execute("INSERT INTO attempts(request_key,started,seconds,status,detail) VALUES(?,?,?,?,?)",
                                (key, started, elapsed, "PROVIDER_ERRORS" if errors else "RESPONSE", str(errors)))
                if not errors:
                    self.db.execute("INSERT OR REPLACE INTO responses VALUES(?,?,?,?,?)",
                                    (key, encoded, source_frame.to_json(orient="split", date_format="iso"),
                                     json.dumps(errors), datetime.now(timezone.utc).isoformat()))
                else:
                    save_text(self.output / "RawErrors" / (key + ".json"),
                              json.dumps({"request": spec, "errors": errors,
                                          "table": json.loads(source_frame.to_json(orient="split", date_format="iso"))}, indent=2))
                self.db.commit()
                if errors and self.is_transient(str(errors)) and attempt < MAX_ATTEMPTS:
                    time.sleep(3)
                    continue
                return frame, errors, key, False
            except StopExtraction as error:
                if not submitted:
                    self.local_errors += 1
                    self.db.execute("INSERT INTO attempts(request_key,started,seconds,status,detail) VALUES(?,?,?,?,?)",
                                    (key, started, time.perf_counter()-begin, "LOCAL_ERROR", str(error)))
                    self.db.commit()
                raise
            except Exception as error:
                elapsed = time.perf_counter() - begin
                if submitted:
                    self.network_seconds += elapsed
                else:
                    self.local_errors += 1
                self.db.execute("INSERT INTO attempts(request_key,started,seconds,status,detail) VALUES(?,?,?,?,?)",
                                (key, started, elapsed, "SDK_ERROR" if submitted else "LOCAL_ERROR", str(error)))
                self.db.commit()
                if not submitted or isinstance(error, (TypeError, AttributeError)):
                    raise StopExtraction("Local SDK compatibility/processing error; no empty-data conclusion: " + str(error)) from error
                self.check_fatal(str(error))
                if self.is_transient(str(error)) and attempt < MAX_ATTEMPTS:
                    print(f"  Temporary error; retry {attempt+1}/{MAX_ATTEMPTS}: {error}", flush=True)
                    time.sleep(3)
                    continue
                return pd.DataFrame(), [str(error)], key, False
            finally:
                stopped.set()
                thread.join(timeout=1)

    @staticmethod
    def is_transient(message):
        return bool(re.search(r"timeout|timed out|429|502|503|504|temporarily|server busy", message, re.I))

    @staticmethod
    def check_fatal(message):
        if re.search(r"session.*not open|session.*closed|no proxy|handshake|connection refused|10061|401|token.*expired", message, re.I):
            raise StopExtraction("LSEG connection/session is unavailable. Open and sign in to Workspace. " + message)

    def progress(self, label, status, rows, cached):
        self.completed += 1
        elapsed = time.perf_counter() - self.started
        if self.calls >= 3:
            # An estimate for NEW requests: cached replies must not imply future calls are instant.
            remaining = self.total - self.completed
            estimate = duration(remaining * (self.network_seconds / self.calls + PAUSE_SECONDS))
        else:
            estimate = "estimating after 3 network calls"
        print(f"[{self.completed}/{self.total}] {label}: {status}, {rows} rows"
              f"{' [CACHE]' if cached else ''} | elapsed {duration(elapsed)} | ETA ~{estimate}", flush=True)


def find_column(frame, code):
    """Match the requested field name; do not guess a value column by position."""
    def norm(value):
        return re.sub(r"\s+", "", str(value)).casefold()
    matches = [c for c in frame.columns if norm(c) == norm(code)]
    return matches[0] if len(matches) == 1 else None


def parse_date(value):
    if value is None or pd.isna(value) or isinstance(value, (int, float)):
        return None
    stamp = pd.to_datetime(value, errors="coerce", utc=True)
    return stamp.date().isoformat() if pd.notna(stamp) else None


def normalize(frame, company, metric, code, key, errors, first_year, last_year):
    if frame.empty and errors:
        return [], "REQUEST_ERROR"
    value_col = find_column(frame, code)
    # Standardised TR.F.* .date denotes the fiscal period end. The legacy
    # TR.* family exposes .periodenddate separately from its provider .date.
    suffix = ".date" if metric == "market_cap" or code.upper().startswith("TR.F.") else ".periodenddate"
    period_col = find_column(frame, code + suffix)
    date_col = find_column(frame, code + ".date")
    if value_col is None or period_col is None:
        return [], "UNRECOGNIZED_COLUMNS" if len(frame) else "EMPTY_RESPONSE"
    observations = []
    for index, record in enumerate(frame.to_dict("records")):
        period = parse_date(record.get(period_col))
        if not period:
            continue
        if metric == "market_cap":
            if not MARKET_START <= period <= MARKET_END:
                continue
        elif not first_year <= int(period[:4]) <= last_year:
            continue
        value = record.get(value_col)
        if value is None or pd.isna(value) or str(value).strip().lower() in {"", "nan", "null", "none", "<na>"}:
            continue
        is_date = metric.endswith("_announcement")
        number = pd.to_numeric(value, errors="coerce") if not is_date else float("nan")
        date_value = parse_date(value) if is_date else None
        if is_date and not date_value:
            continue
        if not is_date and (pd.isna(number) or not math.isfinite(float(number))):
            continue
        observations.append({
            "ticker": company["ticker"], "ric": company["ric"], "expected_company": company["company"],
            "expected_isin": company["isin"], "metric": metric, "provider_field": code,
            "period_end": period, "provider_date": parse_date(record.get(date_col)) if date_col else None,
            "numeric_value": None if is_date else float(number), "date_value": date_value,
            "raw_value": str(value), "requested_currency": "" if is_date else "USD", "requested_scale": 0,
            "requested_reporting_state": "not_applicable" if metric == "market_cap" else "Orig",
            "period_date_kind": "market_observation" if metric == "market_cap" else "provider_fiscal_period_end",
            "source_row": index, "request_key": key, "provider_errors": json.dumps(errors),
        })
    return observations, ("DATA_WITH_PROVIDER_ERRORS" if errors else "DATA") if observations else "NO_USABLE_VALUES"


def reference_check(client, company):
    fields = ["TR.CommonName", "TR.ISIN"]
    frame, errors, key, cached = client.request(company["ric"], fields, {}, company["ticker"] + " identity")
    col = find_column(frame, "TR.ISIN")
    isins = sorted(set(frame[col].dropna().astype(str)) - {""}) if col else []
    expected = company["isin"]
    status = "ISIN_MATCH_CANDIDATE" if expected and isins == [expected] else "IDENTITY_REVIEW"
    if expected and isins and expected not in isins:
        status = "ISIN_MISMATCH"
    client.progress(company["ticker"] + " identity", status, len(frame), cached)
    return {"ticker": company["ticker"], "ric": company["ric"], "expected_company": company["company"],
            "expected_isin": expected, "returned_isins": "|".join(isins), "identity_status": status,
            "provider_errors": str(errors), "request_key": key}


def discover_components(client, company):
    """Only use component codes returned by the provider, never invented codes."""
    frame, errors, key, cached = client.request(
        company["ric"], ["TR.F.BalanceSheet.fieldname", "TR.F.BalanceSheet.fielddescription"],
        {"Period": "FY0"}, "balance-sheet component catalogue")
    client.progress("component catalogue", "RESPONSE" if len(frame) else "UNAVAILABLE", len(frame), cached)
    name_col = find_column(frame, "TR.F.BalanceSheet.fieldname")
    description_col = find_column(frame, "TR.F.BalanceSheet.fielddescription")
    found = {}
    if name_col and description_col and not errors:
        for _, row in frame.iterrows():
            code, description = str(row[name_col]), str(row[description_col])
            # Supplementary source components only; later accounting review is required.
            if re.fullmatch(r"TR\.F\.[A-Za-z0-9]+", code, re.I) and re.search(
                r"preferred.*(?:equity|stock)|deferred.*tax|investment tax credit", description, re.I
            ) and not re.search(r"ratio|percent|per share|per shr|debt.*including", description, re.I):
                found["component__" + code.split(".")[-1]] = code
    save_text(client.output / "component_catalogue.csv", frame.to_csv(index=False))
    # Bounded discovery: do not silently turn a pilot into an entire statement download.
    return dict(sorted(found.items())[:8])


def write_reports(output, companies, jobs, identities, observations, client, state, first_year, last_year):
    data = pd.DataFrame(observations, columns=OBSERVATION_COLUMNS)
    save_text(output / "observations.csv", data.to_csv(index=False))
    save_text(output / "request_report.csv", pd.DataFrame(jobs).to_csv(index=False))
    save_text(output / "identity_report.csv", pd.DataFrame(identities).to_csv(index=False))
    coverage = []
    for company in companies:
        part = data.loc[data.ticker.eq(company["ticker"]) & data.ric.eq(company["ric"])]
        for metric in ANNUAL_FIELDS:
            values = part.loc[part.metric.eq(metric)]
            years = sorted(set(values.period_end.str[:4])) if len(values) else []
            conflicts = int(values.groupby("period_end").raw_value.nunique().gt(1).sum()) if len(values) else 0
            coverage.append({"ticker": company["ticker"], "ric": company["ric"], "metric": metric,
                             "observed_years": "|".join(years), "observed_year_count": len(years),
                             "requested_year_count": last_year-first_year+1,
                             "missing_requested_years": "|".join(str(y) for y in range(first_year,last_year+1) if str(y) not in years),
                             "conflicting_periods": conflicts})
    save_text(output / "coverage_by_company.csv", pd.DataFrame(coverage).to_csv(index=False))
    lines = ["# LSEG Fama-French Input Extraction", "", f"Run state: **{state}**.",
             f"Companies: **{len(companies)}**; jobs completed: **{client.completed}/{client.total}**; "
             f"SDK requests invoked: **{client.calls}**; local errors: **{client.local_errors}**; cache hits: **{client.hits}**; "
             f"elapsed: **{duration(time.perf_counter()-client.started)}**.", "",
             f"SDK version: **{getattr(client.api, '__version__', 'unknown')}**; Python: **{sys.version.split()[0]}**. "
             "SDK requests are not a count of underlying HTTP calls. Constructor failures are local errors.", "",
             f"Script revision: **{SCRIPT_VERSION}**. Script path: `{Path(__file__).resolve()}`. "
             f"Interpreter: `{sys.executable}`.", "",
             f"Annual fiscal period ends requested: **{first_year}-{last_year}**. "
             f"Monthly market-cap observations requested: **{MARKET_START} to {MARKET_END}**.", "",
             "## Input availability in this selected sample", "",
             "| Metric | Companies with values | Earliest date | Latest date | Observations |",
             "| --- | ---: | --- | --- | ---: |"]
    for metric in sorted(set(ANNUAL_FIELDS) | {"market_cap"} | set(data.metric)):
        part = data.loc[data.metric.eq(metric)]
        valid = part.period_end.dropna()
        lines.append(f"| {metric} | {part[['ticker','ric']].drop_duplicates().shape[0]}/{len(companies)} | "
                     f"{valid.min() if len(valid) else '-'} | {valid.max() if len(valid) else '-'} | {len(part)} |")
    lines += ["", "## Interpretation", "",
              "- A bounded, deliberately mixed pilot; its percentages do not estimate coverage of the full project universe.",
              "- Observed/requested years are source-presence diagnostics, not missing-membership rates. "
              "Years before IPO or after delisting are not automatically errors.",
              "- DATA means numeric, dated source observations were extracted. It does not certify identity, "
              "accounting equivalence, units, annual duration or historical availability.",
              "- Equity definitions and provider cost-of-revenue/interest definitions remain separate. "
              "Preferred/deferred-tax components are optional provider-discovered sources; catalogue failure remains a gap.",
              "- Original announcement dates are separate dated series. Check their correspondence with each statement "
              "before applying a June formation cutoff; fiscal period end is not a publication date.",
              "- ReportingState=Orig is requested; no silent fallback to restated data. This is not proof "
              "that the export reproduces every historical vintage or contains no later corrections.",
              "- Curn=USD and Scale=0 are requested; retain those settings and validate against Workspace "
              "before combining sources. Negative equity is preserved; zero expenses are preserved when explicitly supplied.",
              "- Missing expenses remain missing. No operating-profit, book-equity or FF5-eligibility claim is made.",
              "- Monthly company market cap is aggregated across share classes. Actual returned dates are kept. "
              "Missing December/June anchors or post-delisting values require review; no filling is applied.",
              "- Raw responses and request specifications are in extraction.sqlite. API errors are retained in attempts "
              "and RawErrors. Failed requests retry on another run; error-free empty responses are cached until --refresh.",
              "- Matching ISINs are an identity check, not independent confirmation of every historical company-year.",
              "- Historical market/RF factors are separate inputs and are not downloaded here.", ""]
    save_text(output / "report.md", "\n".join(lines))


def run(args):
    print(f"SCRIPT REVISION: {SCRIPT_VERSION}\nScript file: {Path(__file__).resolve()}\nPython executable: {sys.executable}", flush=True)
    companies = load_companies(args.input, args.limit, args.all)
    output = Path(args.output).resolve() if args.output else default_output()
    print(f"BOUNDED PILOT: {len(companies)} companies" if not args.all else f"EXPLICIT INPUT: {len(companies)} companies", flush=True)
    print(f"Output: {output}\nAccounting period ends: {args.first_year}-{args.last_year}\n"
          f"Market cap: monthly, {MARKET_START} to {MARKET_END}\n"
          "Open LSEG Workspace and sign in. Completed calls will be reused.", flush=True)
    try:
        import lseg.data as ld
    except ImportError as error:
        raise SystemExit("Install on this PC first: pip install lseg-data pandas") from error
    client = Downloader(ld, output, args.refresh)
    jobs, observations, identities = [], [], []
    state, opened = "STARTING", False
    fields = dict(ANNUAL_FIELDS)
    try:
        print("Opening LSEG session...", flush=True)
        ld.open_session()
        opened = True
        print(f"LSEG SDK {getattr(ld, '__version__', 'unknown')} | Python {sys.version.split()[0]}", flush=True)
        print("LSEG Definition signature: " + str(inspect.signature(ld.content.fundamental_and_reference.Definition)), flush=True)
        client.total = 1 + len(companies) * (len(fields) + 2)
        optional = discover_components(client, companies[0])
        fields.update(optional)
        client.total = 1 + len(companies) * (len(fields) + 2)
        print(f"Plan: {client.total} jobs, including {len(optional)} provider-discovered component fields. "
              "ETA is an estimate based on new network requests, not cache speed.", flush=True)
        annual_parameters = {"SDate": f"{args.first_year}-01-01", "EDate": datetime.now().date().isoformat(),
                             "Period": "FY0", "Frq": "FY", "Curn": "USD", "Scale": 0,
                             "ReportingState": "Orig", "FXRate": "PeriodEnd"}
        for company in companies:
            identity = reference_check(client, company)
            identities.append(identity)
            if identity["identity_status"] == "ISIN_MISMATCH":
                print(f"  SKIP {company['ticker']}: returned ISIN differs from expected historical security.", flush=True)
                client.total -= len(fields) + 1
                write_reports(output, companies, jobs, identities, observations, client, "RUNNING", args.first_year, args.last_year)
                continue
            for metric, code in {**fields, "market_cap": "TR.CompanyMarketCap"}.items():
                label = f"{company['ticker']} / {metric}"
                parameters = ({"SDate": MARKET_START, "EDate": MARKET_END, "Frq": "M", "Curn": "USD", "Scale": 0}
                              if metric == "market_cap" else annual_parameters)
                requested = [code, code + ".date"]
                if metric != "market_cap" and not code.upper().startswith("TR.F."):
                    requested.append(code + ".periodenddate")
                frame, errors, key, cached = client.request(company["ric"], requested, parameters, label)
                parsed, status = normalize(frame, company, metric, code, key, errors, args.first_year, args.last_year)
                observations.extend(parsed)
                jobs.append({"ticker": company["ticker"], "ric": company["ric"], "metric": metric,
                             "provider_field": code, "status": status, "rows": len(parsed), "cached": cached,
                             "request_key": key, "errors": json.dumps(errors), "returned_columns": "|".join(frame.columns),
                             "raw_returned_columns": "|".join(frame.attrs.get("original_columns", frame.columns))})
                client.progress(label, status, len(parsed), cached)
            # One company's results survive interruption without holding open CSVs.
            write_reports(output, companies, jobs, identities, observations, client, "RUNNING", args.first_year, args.last_year)
            core = [j for j in jobs if j['metric'] in CORE_METRICS]
            if len(identities) >= 2 and not any(j['rows'] for j in core):
                raise StopExtraction("No usable core accounting values for the first two companies. "
                                     "Stopping the pilot; inspect request_report.csv for fields/entitlements/parameters.")
        state = "FINISHED_REQUESTS_REVIEW_REQUIRED"
    except KeyboardInterrupt:
        state = "INTERRUPTED_CHECKPOINTS_SAVED"
        print("\nInterrupted. Completed API responses remain cached.", flush=True)
    except Exception as error:
        state = "STOPPED: " + str(error)
        print("\n" + state, flush=True)
    finally:
        try:
            write_reports(output, companies, jobs, identities, observations, client, state, args.first_year, args.last_year)
            print(f"\n{state}\nElapsed: {duration(time.perf_counter()-client.started)}\nRead: {output/'report.md'}", flush=True)
        finally:
            client.close()
            if opened:
                try:
                    ld.close_session()
                except Exception as error:
                    print(f"Session-close message: {error}", flush=True)
    return 0 if state == "FINISHED_REQUESTS_REVIEW_REQUIRED" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="One-file LSEG FF input extraction; defaults to 20-company pilot.")
    parser.add_argument("--input", help="Optional CSV with explicit ticker/ric mappings")
    parser.add_argument("--all", action="store_true", help="Process every non-empty mapping in --input; explicit opt-in")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--first-year", type=int, default=FIRST_FISCAL_YEAR)
    parser.add_argument("--last-year", type=int, default=LAST_FISCAL_YEAR)
    parser.add_argument("--output", help="Optional output directory")
    parser.add_argument("--refresh", action="store_true", help="Request again instead of reusing saved responses")
    arguments = parser.parse_args()
    if arguments.limit < 1 or arguments.first_year > arguments.last_year:
        parser.error("Use a positive limit and first-year <= last-year.")
    sys.exit(run(arguments))
