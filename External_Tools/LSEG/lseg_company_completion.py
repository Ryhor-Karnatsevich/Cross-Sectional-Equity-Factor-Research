"""Second targeted LSEG recovery: remaining gaps across all company-data fronts.

Run on the same Workspace computer:
    py -3.12 lseg_company_completion.py

One portable file, pandas + lseg-data, Python 3.12. Same working public get_data
interface, explicit FY labels, ReportingState=Orig, USD, Scale=0, batched calls.
Input folders: lseg_company_data_output AND lseg_company_recovery_output.
Default output: lseg_company_completion_output beside this script.
--original PATH / --source PATH override inputs. --plan-only uses no network.
Existing files are read-only. Response caches are reused, including empty replies.
--retry-empty rechecks saved empty replies. --approved-mapping accepts explicit
approved ticker,ric,isin,approved rows; ambiguous identities are never approved.

Fronts: unresolved IDs and ISIN conflicts; missing financial amounts; whole income
and balance templates with provider definitions; publication-period reconciliation;
revenue/gross-profit reconstruction candidates; precise month-end capitalization.
All alternatives, identity candidates, components and calculations retain review
labels. No automatic zero filling, missing-to-not-applicable conversion, replacement
of industry expenses, corporate-successor splicing, or certified PIT claims.

Whole-template interface and fields documented by LSEG:
https://developers.lseg.com/en/article-catalog/article/fundamentals-estimates-dcf
https://developers.lseg.com/en/article-catalog/article/analysing-sp500-companies-stocks-with-beneish-m-score-and-altman-z-score
https://community.developers.lseg.com/discussion/81795
"""
import argparse

from collections import defaultdict

import hashlib

import inspect

import json

import math

import os

from pathlib import Path

import re

import sqlite3

import sys

import threading

import time

import traceback

import unicodedata

import uuid

import pandas as pd

VERSION = "2026-11-18-all-fronts-v1"
# NYSE/S&P trading-calendar month ends from the existing project dataset.
MONTH_ENDS = {'2008-01': '2008-01-31', '2008-02': '2008-02-29', '2008-03': '2008-03-31', '2008-04': '2008-04-30', '2008-05': '2008-05-30', '2008-06': '2008-06-30', '2008-07': '2008-07-31', '2008-08': '2008-08-29', '2008-09': '2008-09-30', '2008-10': '2008-10-31', '2008-11': '2008-11-28', '2008-12': '2008-12-31', '2009-01': '2009-01-30', '2009-02': '2009-02-27', '2009-03': '2009-03-31', '2009-04': '2009-04-30', '2009-05': '2009-05-29', '2009-06': '2009-06-30', '2009-07': '2009-07-31', '2009-08': '2009-08-31', '2009-09': '2009-09-30', '2009-10': '2009-10-30', '2009-11': '2009-11-30', '2009-12': '2009-12-31', '2010-01': '2010-01-29', '2010-02': '2010-02-26', '2010-03': '2010-03-31', '2010-04': '2010-04-30', '2010-05': '2010-05-28', '2010-06': '2010-06-30', '2010-07': '2010-07-30', '2010-08': '2010-08-31', '2010-09': '2010-09-30', '2010-10': '2010-10-29', '2010-11': '2010-11-30', '2010-12': '2010-12-31', '2011-01': '2011-01-31', '2011-02': '2011-02-28', '2011-03': '2011-03-31', '2011-04': '2011-04-29', '2011-05': '2011-05-31', '2011-06': '2011-06-30', '2011-07': '2011-07-29', '2011-08': '2011-08-31', '2011-09': '2011-09-30', '2011-10': '2011-10-31', '2011-11': '2011-11-30', '2011-12': '2011-12-30', '2012-01': '2012-01-31', '2012-02': '2012-02-29', '2012-03': '2012-03-30', '2012-04': '2012-04-30', '2012-05': '2012-05-31', '2012-06': '2012-06-29', '2012-07': '2012-07-31', '2012-08': '2012-08-31', '2012-09': '2012-09-28', '2012-10': '2012-10-31', '2012-11': '2012-11-30', '2012-12': '2012-12-31', '2013-01': '2013-01-31', '2013-02': '2013-02-28', '2013-03': '2013-03-28', '2013-04': '2013-04-30', '2013-05': '2013-05-31', '2013-06': '2013-06-28', '2013-07': '2013-07-31', '2013-08': '2013-08-30', '2013-09': '2013-09-30', '2013-10': '2013-10-31', '2013-11': '2013-11-29', '2013-12': '2013-12-31', '2014-01': '2014-01-31', '2014-02': '2014-02-28', '2014-03': '2014-03-31', '2014-04': '2014-04-30', '2014-05': '2014-05-30', '2014-06': '2014-06-30', '2014-07': '2014-07-31', '2014-08': '2014-08-29', '2014-09': '2014-09-30', '2014-10': '2014-10-31', '2014-11': '2014-11-28', '2014-12': '2014-12-31', '2015-01': '2015-01-30', '2015-02': '2015-02-27', '2015-03': '2015-03-31', '2015-04': '2015-04-30', '2015-05': '2015-05-29', '2015-06': '2015-06-30', '2015-07': '2015-07-31', '2015-08': '2015-08-31', '2015-09': '2015-09-30', '2015-10': '2015-10-30', '2015-11': '2015-11-30', '2015-12': '2015-12-31', '2016-01': '2016-01-29', '2016-02': '2016-02-29', '2016-03': '2016-03-31', '2016-04': '2016-04-29', '2016-05': '2016-05-31', '2016-06': '2016-06-30', '2016-07': '2016-07-29', '2016-08': '2016-08-31', '2016-09': '2016-09-30', '2016-10': '2016-10-31', '2016-11': '2016-11-30', '2016-12': '2016-12-30', '2017-01': '2017-01-31', '2017-02': '2017-02-28', '2017-03': '2017-03-31', '2017-04': '2017-04-28', '2017-05': '2017-05-31', '2017-06': '2017-06-30', '2017-07': '2017-07-31', '2017-08': '2017-08-31', '2017-09': '2017-09-29', '2017-10': '2017-10-31', '2017-11': '2017-11-30', '2017-12': '2017-12-29', '2018-01': '2018-01-31', '2018-02': '2018-02-28', '2018-03': '2018-03-29', '2018-04': '2018-04-30', '2018-05': '2018-05-31', '2018-06': '2018-06-29', '2018-07': '2018-07-31', '2018-08': '2018-08-31', '2018-09': '2018-09-28', '2018-10': '2018-10-31', '2018-11': '2018-11-30', '2018-12': '2018-12-31', '2019-01': '2019-01-31', '2019-02': '2019-02-28', '2019-03': '2019-03-29', '2019-04': '2019-04-30', '2019-05': '2019-05-31', '2019-06': '2019-06-28', '2019-07': '2019-07-31', '2019-08': '2019-08-30', '2019-09': '2019-09-30', '2019-10': '2019-10-31', '2019-11': '2019-11-29', '2019-12': '2019-12-31', '2020-01': '2020-01-31', '2020-02': '2020-02-28', '2020-03': '2020-03-31', '2020-04': '2020-04-30', '2020-05': '2020-05-29', '2020-06': '2020-06-30', '2020-07': '2020-07-31', '2020-08': '2020-08-31', '2020-09': '2020-09-30', '2020-10': '2020-10-30', '2020-11': '2020-11-30', '2020-12': '2020-12-31', '2021-01': '2021-01-29', '2021-02': '2021-02-26', '2021-03': '2021-03-31', '2021-04': '2021-04-30', '2021-05': '2021-05-28', '2021-06': '2021-06-30', '2021-07': '2021-07-30', '2021-08': '2021-08-31', '2021-09': '2021-09-30', '2021-10': '2021-10-29', '2021-11': '2021-11-30', '2021-12': '2021-12-31', '2022-01': '2022-01-31', '2022-02': '2022-02-28', '2022-03': '2022-03-31', '2022-04': '2022-04-29', '2022-05': '2022-05-31', '2022-06': '2022-06-30', '2022-07': '2022-07-29', '2022-08': '2022-08-31', '2022-09': '2022-09-30', '2022-10': '2022-10-31', '2022-11': '2022-11-30', '2022-12': '2022-12-30', '2023-01': '2023-01-31', '2023-02': '2023-02-28', '2023-03': '2023-03-31', '2023-04': '2023-04-28', '2023-05': '2023-05-31', '2023-06': '2023-06-30', '2023-07': '2023-07-31', '2023-08': '2023-08-31', '2023-09': '2023-09-29', '2023-10': '2023-10-31', '2023-11': '2023-11-30', '2023-12': '2023-12-29', '2024-01': '2024-01-31', '2024-02': '2024-02-29', '2024-03': '2024-03-28', '2024-04': '2024-04-30', '2024-05': '2024-05-31', '2024-06': '2024-06-28', '2024-07': '2024-07-31', '2024-08': '2024-08-30', '2024-09': '2024-09-30', '2024-10': '2024-10-31', '2024-11': '2024-11-29', '2024-12': '2024-12-31', '2025-01': '2025-01-31', '2025-02': '2025-02-28', '2025-03': '2025-03-31', '2025-04': '2025-04-30', '2025-05': '2025-05-30', '2025-06': '2025-06-30', '2025-07': '2025-07-31', '2025-08': '2025-08-29', '2025-09': '2025-09-30', '2025-10': '2025-10-31', '2025-11': '2025-11-28', '2025-12': '2025-12-31', '2026-01': '2026-01-30', '2026-02': '2026-02-27', '2026-03': '2026-03-31', '2026-04': '2026-04-30', '2026-05': '2026-05-29', '2026-06': '2026-06-30', '2026-07': '2026-07-31', '2007-12': '2007-12-31'}

BATCH_SIZE = 20

ANNUAL_FIELDS = {
    "total_assets": ("TR.TotalAssetsReported", "periodenddate", "number"),
    "revenue": ("TR.TotalRevenue", "periodenddate", "number"),
    "cost_of_sales_provider": ("TR.CostofRevenueTotal", "periodenddate", "number"),
    "sga": ("TR.SgaExpenseTotal", "periodenddate", "number"),
    "interest_expense_provider": ("TR.InterestExpense", "periodenddate", "number"),
    "common_equity_provider": ("TR.F.ShHoldEqCom", "date", "number"),
    "total_equity_provider": ("TR.TotalEquity", "periodenddate", "number"),
    "minority_interest_provider": ("TR.F.MinIntr", "date", "number"),
    "income_announcement": ("TR.ISOriginalAnnouncementDate", "periodenddate", "date"),
    "balance_announcement": ("TR.BSOriginalAnnouncementDate", "periodenddate", "date"),
}

OBS_COLUMNS = [
    "ticker", "ric", "metric", "field", "requested_fiscal_year", "period_end",
    "observation_date", "numeric_value", "announcement_date", "raw_value",
    "currency_requested", "reporting_state_requested", "date_status",
    "source_row", "request_key",
]

def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"

def save_text(path, content):
    """An open Excel report must not destroy an otherwise completed download."""
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(content, encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8")
    try:
        os.replace(temporary, path)
    except PermissionError:
        path = path.with_name(path.stem + "_latest_" + uuid.uuid4().hex[:8] + path.suffix)
        os.replace(temporary, path)
        print(f"Report locked; saved {path.name} instead.", flush=True)
    return path

def column_key(column):
    # HeaderType.NAME may include inline field parameters and .value.
    name = str(column).split("|")[0].strip().lower()
    name = re.sub(r"\([^)]*\)", "", name)
    return name.removesuffix(".value")

def find_column(frame, name):
    matches = [i for i, column in enumerate(frame.columns) if column_key(column) == name.lower()]
    return matches[0] if len(matches) == 1 else None

def iso_date(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return ""
    # Numeric 2018 must not be interpreted as nanoseconds since 1970.
    if isinstance(value, (int, float)):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(parsed) else parsed.date().isoformat()

def parse_observations(frame, companies, metric, field, date_property, kind, year, key):
    """Keep the field's own period date; never align different metrics by row number."""
    instrument = find_column(frame, "instrument")
    value_column = find_column(frame, field)
    date_column = find_column(frame, field + "." + date_property)
    if instrument is None or value_column is None:
        return [], "RAW_DATA_UNPARSED"
    by_ric = companies.groupby("ric")["ticker"].agg(list).to_dict()
    rows = []
    for source_row, values in enumerate(frame.itertuples(index=False, name=None)):
        ric, value = str(values[instrument]), values[value_column]
        if ric not in by_ric or pd.isna(value) or str(value).strip() == "":
            continue
        date = iso_date(values[date_column]) if date_column is not None else ""
        numeric = pd.to_numeric(value, errors="coerce") if kind == "number" else None
        announcement = iso_date(value) if kind == "date" else ""
        if (kind == "number" and pd.isna(numeric)) or (kind == "date" and not announcement):
            continue
        rows.append({
            "ticker": by_ric[ric][0], "ric": ric, "metric": metric, "field": field,
            "requested_fiscal_year": year, "period_end": date if year else "",
            "observation_date": date if not year else "", "numeric_value": numeric,
            "announcement_date": announcement, "raw_value": str(value),
            "currency_requested": "USD" if kind == "number" else "",
            "reporting_state_requested": "Orig" if year else "",
            "date_status": "DATED" if date else "MISSING_DATE_REVIEW",
            "source_row": source_row, "request_key": key,
        })
        for alias in by_ric[ric][1:]:
            rows.append({**rows[-1], "ticker": alias})
    if not rows:
        return [], "NO_USABLE_VALUES"
    status = "EXTRACTED" if all(r["date_status"] == "DATED" for r in rows) else "EXTRACTED_DATE_REVIEW"
    return rows, status

PRIMARY_METRICS = ("total_assets", "common_equity_provider", "revenue",
                   "cost_of_sales_provider", "sga", "interest_expense_provider",
                   "balance_announcement", "income_announcement")

ALTERNATIVES = {
    "total_assets": [("TR.F.TotAssets", "date")],
    "revenue": [("TR.BankTotalRevenue", "periodenddate"),
                ("TR.F.TotRevenue", "date"), ("TR.F.TotRevBizActiv", "date")],
    "cost_of_sales_provider": [("TR.F.COGSTot", "date")],
    "sga": [("TR.F.SGATot", "date")],
    "interest_expense_provider": [("TR.F.IntrExpn", "date")],
}

EXTRA_COLUMNS = ["target_metric", "definition_review_required", "recovery_stage"]

def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)

def company_words(text):
    # KOHLS == Kohl's; MCDONALDS == McDonald's; MOODYS == Moody's.
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"['’‘`]", "", text)
    stop = {"inc", "corp", "corporation", "company", "co", "the", "ltd", "plc",
            "holdings", "group", "ordinary", "share", "shares", "class", "common", "stock"}
    return {word for word in re.findall(r"[a-z0-9]+", text) if len(word) >= 3 and word not in stop}

def name_matches(expected, actual):
    got = company_words(actual)
    # Separate aliases are alternatives, not words all required in one title.
    for alias in str(expected).split("|"):
        wanted = company_words(alias)
        if wanted and wanted.issubset(got):
            return True
    return False

def choose_identity(company, records, capped=False):
    groups = defaultdict(list)
    for row in records:
        if not row.get("RIC") or not name_matches(company.get("company", ""), row.get("DocumentTitle", "")):
            continue
        issued, retired = iso_date(row.get("IssueDate")), iso_date(row.get("RetireDate"))
        first, last = company.get("first_membership_date", ""), company.get("last_membership_date", "")
        if (issued and last and issued > last) or (retired and first and retired < first):
            continue
        identity = row.get("ISIN") or row.get("IssueISIN") or row["RIC"]
        groups[identity].append(row)
    if capped or len(groups) != 1:
        return None, "SEARCH_CAPPED_REVIEW" if capped else "AMBIGUOUS_OR_UNMATCHED_REVIEW"
    entries = next(iter(groups.values()))
    entries.sort(key=lambda row: (str(row.get("IsPrimaryIssueRIC", "")).lower() != "true", len(row["RIC"]), row["RIC"]))
    chosen = entries[0]
    return {**company, "ric": chosen["RIC"], "isin": chosen.get("ISIN") or chosen.get("IssueISIN") or "",
            "provider_company": chosen.get("DocumentTitle", ""), "mapping_status": "NORMALIZED_NAME_SINGLE_SECURITY_CANDIDATE"}, "RECOVERED_IDENTITY_CANDIDATE"

class Client:
    """Same working public SDK interface, with durable raw responses and ETA."""
    def __init__(self, ld, root, retry_empty=False):
        self.ld, self.root, self.retry_empty = ld, root, retry_empty
        self.db = sqlite3.connect(root / "recovery_raw.sqlite")
        self.db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, request TEXT, payload TEXT, retrieved_at TEXT)")
        self.logs, self.calls, self.seconds = [], 0, 0.
        self.started = time.perf_counter()
        self.phase, self.done, self.total, self.failures = "", 0, 0, 0

    def start_phase(self, name, total):
        self.phase, self.done, self.total = name, 0, total
        print(f"\n{name}: {total} jobs", flush=True)

    def call(self, rics, fields, parameters, label):
        request = {"universe": list(dict.fromkeys(rics)), "fields": fields, "parameters": parameters}
        encoded = json.dumps(request, sort_keys=True)
        key = hashlib.sha256((VERSION + encoded).encode()).hexdigest()
        cached = self.db.execute("SELECT payload FROM responses WHERE key=?", (key,)).fetchone()
        frame = None
        if cached:
            raw = json.loads(cached[0])
            frame = pd.DataFrame(raw["data"], columns=raw["columns"])
            if self.retry_empty:
                value_fields = [field for field in fields if not field.lower().endswith((".date", ".periodenddate", ".fperiod"))]
                positions = [find_column(frame, field) for field in value_fields]
                has_value = any(position is not None and (frame.iloc[:, position].notna()
                                & frame.iloc[:, position].astype(str).str.strip().ne("")).any() for position in positions)
                if frame.empty or not has_value:
                    frame = None
        entry = {"request_key": key, "phase": self.phase, "label": label,
                 "source": "CACHE" if frame is not None else "SDK", "status": "", "error": "",
                 "fields": json.dumps(fields), "parameters": json.dumps(parameters), "universe": json.dumps(request["universe"])}
        self.done += 1
        print(f"[{self.phase} {self.done}/{self.total}] {label} ({entry['source']})", flush=True)
        before = time.perf_counter()
        if frame is None:
            stopped = threading.Event()
            def heartbeat():
                while not stopped.wait(15):
                    print(f"  Waiting for LSEG: {label}, {duration(time.perf_counter() - before)}", flush=True)
            thread = threading.Thread(target=heartbeat, daemon=True)
            thread.start()
            try:
                for attempt in range(2):
                    try:
                        self.calls += 1
                        frame = self.ld.get_data(**request, header_type=self.ld.HeaderType.NAME)
                        if not isinstance(frame, pd.DataFrame):
                            raise TypeError(f"Expected DataFrame, got {type(frame).__name__}")
                        self.failures = 0
                        break
                    except (TypeError, AttributeError):
                        # A programming/SDK mismatch is not an unavailable company.
                        raise
                    except Exception as error:
                        entry["error"] = f"{type(error).__name__}: {error}"
                        transient = any(word in str(error).lower() for word in ("backend", "timeout", "timed out", "429", "503", "502", "504"))
                        if attempt == 0 and transient:
                            print("  Transient/backend error; retrying once...", flush=True)
                            time.sleep(2)
                            continue
                        frame = pd.DataFrame()
                        entry["status"] = "REQUEST_ERROR"
                        connection_failure = any(word in str(error).lower() for word in (
                            "session is not opened", "session is not open", "connection refused",
                            "no proxy", "unauthorized", "401", "403", "10061"))
                        self.failures = self.failures + 1 if connection_failure else 0
                        with (self.root / "errors.log").open("a", encoding="utf-8") as stream:
                            stream.write(f"\n{label}\n{encoded}\n{traceback.format_exc()}\n")
                        print("  " + entry["error"], flush=True)
                if entry["status"] != "REQUEST_ERROR":
                    entry["error"] = ""
                    self.db.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?)", (
                        key, encoded, frame.to_json(orient="split", date_format="iso", default_handler=str),
                        pd.Timestamp.now(tz="UTC").isoformat()))
                    self.db.commit()
            finally:
                stopped.set()
                thread.join()
                self.seconds += time.perf_counter() - before
        entry["status"] = entry["status"] or ("RAW_SAVED" if not frame.empty else "EMPTY_RESPONSE")
        entry["rows"] = len(frame)
        entry["seconds"] = round(time.perf_counter() - before, 3)
        self.logs.append(entry)
        # Persist the small log too; the raw cache is committed before parsing.
        save_text(self.root / "request_report.csv", pd.DataFrame(self.logs).to_csv(index=False))
        remaining = max(0, self.total - self.done)
        eta = duration(remaining * self.seconds / self.calls) if self.calls >= 3 else "estimating"
        print(f"  {entry['status']}: {len(frame)} rows | elapsed {duration(time.perf_counter() - self.started)} | phase ETA ~{eta}", flush=True)
        if self.failures >= 6:
            raise RuntimeError("Six consecutive failed SDK calls. Stopped to avoid running a disconnected/denied plan; completed responses are saved.")
        time.sleep(0.15 if entry["source"] == "SDK" else 0)
        return frame, key, entry

def resolve_companies(ld, universe, selected, source, root, approved=None):
    known = selected.set_index("ticker").to_dict("index")
    overrides = {}
    if approved:
        custom = read_csv(approved)
        if not {"ticker", "ric", "isin", "approved"}.issubset(custom.columns):
            raise ValueError("Approved mapping CSV requires ticker,ric,isin,approved columns.")
        custom = custom.loc[custom.approved.str.lower().isin(["true", "1", "yes"])]
        if custom.ticker.duplicated().any():
            raise ValueError("Approved mapping has duplicate tickers.")
        if custom.ric.str.strip().eq("").any() or custom["isin"].str.strip().eq("").any():
            raise ValueError("Approved mapping needs nonempty ric and isin for every approved row.")
        overrides = custom.set_index("ticker").to_dict("index")
    old_path = source / "identifier_search.json"
    cached = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    new_path = root / "identifier_search.json"
    previous = json.loads(new_path.read_text(encoding="utf-8")) if new_path.exists() else {}
    result, review = [], []
    unresolved = [r for r in universe.to_dict("records") if r["ticker"] not in known]
    print(f"Identifier recovery: {len(unresolved)} unresolved tickers; reuse previous search results first.", flush=True)
    for company in universe.to_dict("records"):
        ticker = company["ticker"]
        if ticker in overrides:
            result.append({**company, **overrides[ticker], "mapping_status": "USER_APPROVED_MAPPING"})
            continue
        if ticker in known:
            result.append({**company, **known[ticker]})
            continue
        item = previous.get(ticker) or cached.get(ticker) or {"records": [], "capped": False}
        chosen, status = choose_identity(company, item.get("records", []), item.get("capped", False))
        # Repeat the SAME stock search, but try the company query when ticker
        # matches are unrelated (e.g. a reused symbol), not only when raw is empty.
        if chosen is None and ld is not None and (ticker not in previous or previous[ticker].get("errors")):
            escaped = ticker.replace("'", "''")
            variants = list(dict.fromkeys([escaped, escaped.replace("-", ".")]))
            stock_filter = ("BusinessEntity eq 'QUOTExEQUITY' and ExchangeCountry eq 'USA' and "
                            "(RCSAssetCategoryLeaf eq 'Ordinary Share' or RCSAssetCategoryLeaf eq 'American Depository Receipt' or RCSAssetCategoryLeaf eq 'Depository Receipt')")
            symbol_filter = " or ".join(f"TickerSymbol xeq '{value}'" for value in variants)
            searches = [(None, stock_filter + f" and ({symbol_filter})")]
            searches.extend((alias.strip(), stock_filter) for alias in company.get("company", "").split("|") if alias.strip())
            records, errors, capped = [], [], False
            # Reuse properties actually returned by this account's old search.
            observed_fields = {field for data in cached.values() for row in data.get("records", []) for field in row}
            desired = ["RIC", "DocumentTitle", "TickerSymbol", "ISIN", "IssueISIN", "IssueDate", "RetireDate", "IsPrimaryIssueRIC"]
            fields = [field for field in desired if field in observed_fields] if observed_fields else desired
            if not {"RIC", "DocumentTitle"}.issubset(fields):
                raise ValueError("Previous search schema has no RIC/DocumentTitle; inspect identifier_search.json.")
            select = ",".join(fields)
            for query, filters in searches:
                kwargs = {"view": ld.discovery.Views.EQUITY_QUOTES, "filter": filters, "select": select, "top": 100}
                if query:
                    kwargs["query"] = query
                try:
                    frame = ld.discovery.search(**kwargs)
                    if frame is not None and not frame.empty:
                        capped |= len(frame) >= 100
                        records.extend(json.loads(frame.to_json(orient="records", date_format="iso")))
                except Exception as error:
                    errors.append(f"{type(error).__name__}: {error}")
                time.sleep(0.2)
            item = {"records": records, "capped": capped, "errors": errors}
            previous[ticker] = item
            save_text(new_path, json.dumps(previous, ensure_ascii=False, indent=2))
            chosen, status = choose_identity(company, records, capped)
            if errors:
                chosen, status = None, "SEARCH_ERROR_REVIEW"
        if chosen:
            result.append(chosen)
        review.append({"ticker": ticker, "expected_company": company.get("company", ""), "status": status,
                       "chosen_ric": chosen["ric"] if chosen else "", "search_errors": " | ".join(item.get("errors", [])),
                       "candidates_json": json.dumps(item.get("records", []), ensure_ascii=False)})
        print(f"  {ticker}: {status}" + (f" -> {chosen['ric']}" if chosen else ""), flush=True)
    save_text(root / "identifier_recovery.csv", pd.DataFrame(review).to_csv(index=False))
    companies = pd.DataFrame(result)
    save_text(root / "selected_companies.csv", companies.to_csv(index=False))
    # Preserve the known ISIN mismatches for investigation, never auto-approve.
    identity_path = source / "identities.csv"
    blocked = set()
    if identity_path.exists():
        identities = read_csv(identity_path)
        col = next((c for c in identities if c.lower() == "tr.isin"), None)
        if col:
            test = selected.merge(identities[["Instrument", col]].drop_duplicates(), left_on="ric", right_on="Instrument", how="left")
            mismatches = test.loc[test["isin"].ne("") & test[col].notna() & test[col].ne("") & test["isin"].ne(test[col])]
            blocked = set(mismatches.ticker) - set(overrides)
            save_text(root / "identity_mismatches_review.csv", mismatches.to_csv(index=False))
    return companies, blocked

def observed_keys(frame):
    """A requested FY label is not a substitute for an actual fiscal period end."""
    if frame.empty:
        return set()
    date = pd.to_datetime(frame.period_end, errors="coerce")
    numeric = pd.to_numeric(frame.numeric_value, errors="coerce")
    announced = pd.to_datetime(frame.announcement_date, errors="coerce")
    kind_date = frame.metric.isin(["balance_announcement", "income_announcement"])
    valid = date.notna() & ((~kind_date & numeric.abs().lt(float("inf"))) | (kind_date & announced.notna() & announced.ge(date)))
    return set(zip(frame.loc[valid, "ticker"], frame.loc[valid, "ric"], frame.loc[valid, "metric"], date.loc[valid].dt.year.astype(int)))

def fiscal_shifts(frame):
    dated = frame.loc[frame.requested_fiscal_year.notna()].copy()
    dated["shift"] = pd.to_datetime(dated.period_end, errors="coerce").dt.year - pd.to_numeric(dated.requested_fiscal_year, errors="coerce")
    result = {}
    for key, group in dated.groupby(["ticker", "metric"]):
        counts = group["shift"].dropna().value_counts()
        if not counts.empty and counts.index[0] in (0, 1) and counts.iloc[0] / counts.sum() >= .8:
            result[key] = int(counts.index[0])
    return result

def build_gaps(companies, baseline, blocked):
    present, shifts = observed_keys(baseline), fiscal_shifts(baseline)
    gaps = []
    for row in companies.to_dict("records"):
        if row["ticker"] in blocked:
            continue
        first = pd.to_datetime(row["first_membership_date"], errors="coerce")
        last = pd.to_datetime(row["last_membership_date"], errors="coerce")
        if pd.isna(first) or pd.isna(last) or first > last:
            continue
        formation_first = first.year - int(first.month < 7)
        formation_last = last.year - int(last.month < 7)
        for metric in PRIMARY_METRICS:
            years = set(range(formation_first - 1, formation_last))
            if metric == "total_assets":
                years.update(range(formation_first - 2, formation_last - 1))
            # Original announcement dates for those earlier asset statements.
            if metric == "balance_announcement":
                years.update(range(formation_first - 2, formation_last - 1))
            for year in sorted(years):
                key = (row["ticker"], row["ric"], metric, year)
                if key not in present:
                    shift = shifts.get((row["ticker"], metric), 0)
                    gaps.append({"ticker": row["ticker"], "ric": row["ric"], "metric": metric,
                                 "required_calendar_year": year, "request_fiscal_year": year - shift,
                                 "fiscal_label_shift": shift})
    return pd.DataFrame(gaps, columns=["ticker", "ric", "metric", "required_calendar_year", "request_fiscal_year", "fiscal_label_shift"])

def annual_jobs(gaps):
    jobs = []
    for (year, metric), group in gaps.groupby(["request_fiscal_year", "metric"], sort=True):
        pairs = group[["ticker", "ric"]].drop_duplicates()
        for i in range(0, len(pairs), BATCH_SIZE):
            jobs.append((int(year), metric, pairs.iloc[i:i + BATCH_SIZE]))
    return jobs

def recover_annual(client, jobs, stage, alternatives=False, collected=None):
    rows = [] if collected is None else collected
    client.start_phase(stage, len(jobs))
    for year, target, pairs in jobs:
        specs = ALTERNATIVES.get(target, []) if alternatives else [ANNUAL_FIELDS[target][:2]]
        if alternatives:
            client.total += max(0, len(specs) - 1)
        for field, date_property in specs:
            kind = "number" if alternatives else ANNUAL_FIELDS[target][2]
            params = {"Period": f"FY{year}", "ReportingState": "Orig"}
            if kind == "number":
                params.update({"Curn": "USD", "Scale": 0})
            def fetch(group):
                frame, key, entry = client.call(group.ric, [field, field + "." + date_property], params, f"FY{year} {target}: {field}, {len(group)} tickers")
                # Try the minimal working request before splitting a failed batch.
                # Unsupported date properties must not produce 20 futile calls.
                if entry["status"] == "REQUEST_ERROR":
                    client.total += 1
                    frame, key, entry = client.call(group.ric, [field], params, f"FY{year} {field}: value-only fallback")
                if entry["status"] == "REQUEST_ERROR" and group.ric.nunique() > 1:
                    # The previously failed common-equity batch is isolated this way.
                    client.total += group.ric.nunique()
                    return [item for _, one in group.groupby("ric", sort=False) for item in fetch(one)]
                # A value-only response still has a useful FY request label, but
                # receives MISSING_DATE_REVIEW and is never counted as dated data.
                if frame.empty:
                    return []
                metric = target + "_alternative_review" if alternatives else target
                parsed, status = parse_observations(frame, group, metric, field, date_property, kind, year, key)
                for item in parsed:
                    item.update({"target_metric": target, "definition_review_required": alternatives, "recovery_stage": stage})
                entry["parse_status"], entry["parsed_values"] = status, len(parsed)
                return parsed
            rows.extend(fetch(pairs))
    return rows

def market_jobs(companies, observations, blocked):
    caps = observations.loc[observations.metric.eq("market_cap") & pd.to_numeric(observations.numeric_value, errors="coerce").gt(0)].copy()
    caps["date"] = pd.to_datetime(caps.observation_date, errors="coerce")
    # Repeated last-known values cannot create later months of coverage.
    caps = caps.loc[caps.date.notna() & caps.date.ge(caps.date + pd.offsets.MonthEnd(0) - pd.Timedelta(days=7))]
    present = set(zip(caps.ticker, caps.ric, caps.date.dt.to_period("M")))
    intervals = defaultdict(list)
    for row in companies.to_dict("records"):
        if row["ticker"] in blocked:
            continue
        first_date = pd.to_datetime(row["first_membership_date"], errors="coerce")
        last_date = pd.to_datetime(row["last_membership_date"], errors="coerce")
        if pd.isna(first_date) or pd.isna(last_date) or first_date > last_date:
            continue
        first = first_date.to_period("M") - 1
        last = last_date.to_period("M") - 1
        missing = [m for m in pd.period_range(first, last, freq="M") if (row["ticker"], row["ric"], m) not in present]
        runs = []
        for month in missing:
            if runs and month == runs[-1][-1] + 1:
                runs[-1].append(month)
            else:
                runs.append([month])
        for run in runs:
            intervals[(str(run[0].end_time.date()), str(run[-1].end_time.date()))].append({"ticker": row["ticker"], "ric": row["ric"]})
    jobs = []
    for (start, end), pairs in sorted(intervals.items()):
        frame = pd.DataFrame(pairs).drop_duplicates()
        for i in range(0, len(frame), BATCH_SIZE):
            jobs.append((start, end, frame.iloc[i:i + BATCH_SIZE]))
    return jobs


# -------------------------
# SECOND RECOVERY: WORKING API AND PREVIOUS RESULTS ARE REUSED
NEW_FIELDS = {
    "cost_of_sales_provider": [("TR.F.CostOfOpRev", "date")],
    "gross_profit_provider": [("TR.F.GrossProfIndPropTot", "date")],
    "revenue_for_reconstruction": [("TR.F.TotRevenue", "date")],
}


def locate_input(name):
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        for candidate in [parent / name, parent / "LSEG_Recovery" / name,
                          parent / "External_Tools/LSEG" / name]:
            if candidate.is_dir():
                return candidate
    return here / name


def normalize_candidates(frame):
    data = frame.copy()
    if "target_metric" in data:
        valid = data.target_metric.notna() & data.target_metric.astype(str).ne("")
        data.loc[valid, "metric"] = data.loc[valid, "target_metric"]
    return data


def seed_response_cache(client, folders):
    """Read old caches without modifying them; preserve raw table/timestamp."""
    count = 0
    for folder in folders:
        for name in ["raw_responses.sqlite", "recovery_raw.sqlite"]:
            path = folder / name
            if not path.is_file():
                continue
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                columns = {r[1] for r in db.execute("PRAGMA table_info(responses)")}
                payload = "payload" if "payload" in columns else "data"
                if not {"request", payload, "retrieved_at"}.issubset(columns):
                    continue
                for request, data, retrieved in db.execute(f"SELECT request,{payload},retrieved_at FROM responses"):
                    encoded = json.dumps(json.loads(request), sort_keys=True)
                    key = hashlib.sha256((VERSION + encoded).encode()).hexdigest()
                    before = client.db.total_changes
                    client.db.execute("INSERT OR IGNORE INTO responses VALUES (?,?,?,?)", (key, encoded, data, retrieved))
                    count += client.db.total_changes - before
                client.db.commit()
            finally:
                db.close()
    print(f"Reused {count} cached raw responses from previous runs.", flush=True)


def execute_fields(client, jobs, stage, collected):
    """jobs: (FY label, target metric, actual field, date property, value kind, ticker/RIC frame)."""
    client.start_phase(stage, len(jobs))
    for year, target, field, prop, kind, pairs in jobs:
        params = {"Period": f"FY{year}", "ReportingState": "Orig"}
        if kind == "number":
            params.update({"Curn": "USD", "Scale": 0})
        def fetch(group):
            table, key, entry = client.call(group.ric, [field, field + "." + prop], params,
                                            f"FY{year} {target}: {field}, {len(group)} labels")
            if entry["status"] == "REQUEST_ERROR":
                client.total += 1
                table, key, entry = client.call(group.ric, [field], params, f"FY{year} {field}: value-only")
            if entry["status"] == "REQUEST_ERROR" and group.ric.nunique() > 1:
                client.total += group.ric.nunique()
                for _, one in group.groupby("ric", sort=False):
                    fetch(one)
                return
            if table.empty:
                return
            parsed, status = parse_observations(table, group, target + "_completion_review", field, prop, kind, year, key)
            for row in parsed:
                row.update({"target_metric": target, "definition_review_required": True, "recovery_stage": stage})
            collected.extend(parsed)
            entry["parse_status"], entry["parsed_values"] = status, len(parsed)
        fetch(pairs)


def batch_specs(gaps, specs):
    jobs = []
    for (year, target), group in gaps.groupby(["request_fiscal_year", "metric"], sort=True):
        pairs = group[["ticker", "ric"]].drop_duplicates()
        for field, prop in specs.get(target, []):
            for i in range(0, len(pairs), BATCH_SIZE):
                jobs.append((int(year), target, field, prop, "number", pairs.iloc[i:i + BATCH_SIZE]))
    return jobs


def publication_plan(companies, data, gaps, blocked):
    """Find unmatched/late dates explicitly, including amounts already present."""
    data = normalize_candidates(data)
    data = data.loc[data.ticker.isin(companies.ticker) & ~data.ticker.isin(blocked)].copy()
    data["period_end"] = pd.to_datetime(data.period_end, errors="coerce")
    data["announcement_date"] = pd.to_datetime(data.announcement_date, errors="coerce")
    dates = data.loc[data.metric.isin(["balance_announcement", "income_announcement"])
                     & data.announcement_date.ge(data.period_end)]
    dates = dates.groupby(["ticker", "ric", "metric", "period_end"]).announcement_date.min().to_dict()
    review, requested = [], set()
    wanted = set(PRIMARY_METRICS) - {"balance_announcement", "income_announcement"}
    for row in data.loc[data.metric.isin(wanted) & data.period_end.notna()
                        & pd.to_numeric(data.numeric_value, errors="coerce").notna()].itertuples():
        metric = "income_announcement" if row.metric in {"revenue", "cost_of_sales_provider", "sga", "interest_expense_provider"} else "balance_announcement"
        published = dates.get((row.ticker, row.ric, metric, row.period_end))
        cutoff = pd.Timestamp(row.period_end.year + 1, 6, 30)
        if published is not None and published <= cutoff:
            continue
        reason = "MISSING_MATCHING_PUBLICATION_DATE" if published is None else "PUBLICATION_AFTER_JUNE_CUTOFF"
        review.append({"ticker": row.ticker, "ric": row.ric, "metric": row.metric,
                       "period_end": row.period_end.date().isoformat(), "reason": reason,
                       "published": "" if published is None else published.date().isoformat(),
                       "cutoff": cutoff.date().isoformat()})
        label = int(row.requested_fiscal_year) if pd.notna(row.requested_fiscal_year) else row.period_end.year
        for year in (label - 1, label, label + 1):
            requested.add((row.ticker, row.ric, metric, year))
    for row in gaps.loc[gaps.metric.isin(["balance_announcement", "income_announcement"])].itertuples():
        for year in (row.request_fiscal_year - 1, row.request_fiscal_year, row.request_fiscal_year + 1):
            requested.add((row.ticker, row.ric, row.metric, int(year)))
    plan = pd.DataFrame(sorted(requested), columns=["ticker", "ric", "metric", "request_fiscal_year"])
    jobs = []
    for year, metric, pairs in annual_jobs(plan):
        field, prop, kind = ANNUAL_FIELDS[metric]
        jobs.append((year, metric, field, prop, kind, pairs))
    return pd.DataFrame(review), jobs


def role_for_field(code, description):
    """Return candidates by provider descriptions, never inferred equivalence."""
    text = re.sub(r"[^a-z0-9]+", " ", description.lower())
    code = code.lower()
    if code in {"tr.f.costofoprev", "tr.f.cogstot"} or re.search(r"cost of (goods|revenues?|sales|operating revenue)", text):
        return "cost_of_sales_provider"
    if "gross profit" in text:
        return "gross_profit_provider"
    if code == "tr.f.sgatot" or ("selling" in text and "general" in text and "administrative" in text):
        return "sga"
    if "general" in text and "administrative" in text and "expense" in text:
        return "sga_general_component"
    if re.search(r"selling|marketing", text) and "expense" in text:
        return "sga_selling_component"
    if "interest expense" in text:
        return "net_interest_context" if "net" in text else "interest_expense_provider"
    if "total revenue" in text or "revenue from business activities total" in text:
        return "revenue"
    if "shareholders equity common" in text or "common shareholders equity" in text:
        return "common_equity_provider"
    if "total assets" in text and not re.search(r"ratio|percent|return|average", text):
        return "total_assets"
    if "preferred" in text and ("equity" in text or "stock" in text):
        return "preferred_equity_component"
    if "minority interest" in text or "non controlling interest" in text:
        return "minority_interest_component"
    if "equity" in text and re.search(r"parent|attributable.*owners", text):
        return "parent_equity_component"
    if "equity" in text and re.search(r"total|including", text):
        return "total_equity_component"
    if "operating expenses" in text:
        return "operating_expenses_context"
    return ""


def get_position(frame, field, aliases=()):
    for name in [field, *aliases]:
        pos = find_column(frame, name)
        if pos is not None:
            return pos
    return None


def parse_template(table, pairs, template, year, key):
    inst = get_position(table, "instrument")
    name = get_position(table, template + ".fieldname", ["name", "fieldname"])
    desc = get_position(table, template + ".fielddescription", ["description", "fielddescription"])
    value = get_position(table, template, ["STD Income Statement All", "STD Balance Sheet All"])
    if any(x is None for x in (inst, name, desc, value)):
        return []
    by_ric = pairs.groupby("ric").ticker.agg(list).to_dict()
    result = []
    for row in table.itertuples(index=False, name=None):
        ric, code, description = str(row[inst]), str(row[name]), str(row[desc])
        if ric not in by_ric or not code.lower().startswith("tr."):
            continue
        for ticker in by_ric[ric]:
            result.append({"ticker": ticker, "ric": ric, "requested_fiscal_year": year,
                           "statement": template, "provider_field": code, "provider_description": description,
                           "raw_value": str(row[value]), "target_metric": role_for_field(code, description),
                           "period_end": "", "date_status": "TEMPLATE_PERIOD_NOT_INFERRED",
                           "currency_requested": "USD", "reporting_state_requested": "Orig", "request_key": key})
    return result


def collect_templates(client, gaps, timing, collected):
    wanted = gaps[["ticker", "ric", "request_fiscal_year", "metric"]].copy()
    if not timing.empty:
        extra = timing.copy()
        extra["request_fiscal_year"] = pd.to_datetime(extra.period_end).dt.year
        wanted = pd.concat([wanted, extra[wanted.columns]], ignore_index=True)
    wanted["template"] = wanted.metric.map(lambda m: "TR.F.BalanceSheet" if m in {"total_assets", "common_equity_provider", "balance_announcement"} else "TR.F.IncomeStatement")
    wanted = wanted.drop_duplicates(["ticker", "ric", "request_fiscal_year", "template"])
    jobs = []
    for (template, year), group in wanted.groupby(["template", "request_fiscal_year"], sort=True):
        pairs = group[["ticker", "ric"]].drop_duplicates()
        for i in range(0, len(pairs), BATCH_SIZE):
            jobs.append((template, int(year), pairs.iloc[i:i + BATCH_SIZE]))
    client.start_phase("WHOLE STATEMENT CAPABILITIES", 6)
    enabled, capabilities = {}, []
    for template in ["TR.F.IncomeStatement", "TR.F.BalanceSheet"]:
        enabled[template] = False
        for ticker, ric in [("CELG", "CELG.O^K19"), ("ATVI", "ATVI.O^J23"), ("JPM", "JPM.N")]:
            pairs = pd.DataFrame({"ticker": [ticker], "ric": [ric]})
            table, key, entry = client.call([ric], [template + ".fieldname", template + ".fielddescription", template],
                                            {"Period": "FY2018", "ReportingState": "Orig", "Curn": "USD", "Scale": 0}, f"{template}: {ric} FY2018")
            parsed = parse_template(table, pairs, template, 2018, key) if not table.empty else []
            enabled[template] |= bool(parsed)
            capabilities.append({"template": template, "ric": ric, "rows_parsed": len(parsed), "status": entry["status"]})
    save_text(client.root / "template_capabilities.csv", pd.DataFrame(capabilities).to_csv(index=False))
    client.start_phase("WHOLE FINANCIAL STATEMENTS", sum(enabled[t] for t, _, _ in jobs))
    for template, year, pairs in jobs:
        if not enabled[template]:
            continue  # Recorded failed capability; documented direct fields still run.
        table, key, entry = client.call(pairs.ric, [template + ".fieldname", template + ".fielddescription", template],
                                        {"Period": f"FY{year}", "ReportingState": "Orig", "Curn": "USD", "Scale": 0},
                                        f"{template} FY{year}, {len(pairs)} labels")
        if not table.empty:
            collected.extend(parse_template(table, pairs, template, year, key))
    return enabled


def discovered_jobs(template_rows, baseline, new_rows):
    table = pd.DataFrame(template_rows)
    if table.empty:
        return []
    seen = set()
    for frame in (baseline, pd.DataFrame(new_rows)):
        if not frame.empty:
            seen.update(zip(frame.ticker, frame.ric, frame.field.str.lower(), pd.to_numeric(frame.requested_fiscal_year, errors="coerce")))
    usable = []
    for row in table.loc[table.target_metric.ne("")].drop_duplicates(["ticker", "ric", "provider_field", "requested_fiscal_year"]).itertuples():
        if (row.ticker, row.ric, row.provider_field.lower(), row.requested_fiscal_year) in seen:
            continue
        usable.append({"ticker": row.ticker, "ric": row.ric, "year": int(row.requested_fiscal_year),
                       "field": row.provider_field, "target": row.target_metric})
    jobs = []
    if usable:
        for (year, target, field), group in pd.DataFrame(usable).groupby(["year", "target", "field"], sort=True):
            pairs = group[["ticker", "ric"]].drop_duplicates()
            for i in range(0, len(pairs), BATCH_SIZE):
                jobs.append((int(year), target, field, "date" if field.lower().startswith("tr.f.") else "periodenddate", "number", pairs.iloc[i:i + BATCH_SIZE]))
    return jobs


def reconstruction_candidates(data):
    """Calculations are kept outside downloaded observations and require review."""
    if data.empty:
        return pd.DataFrame()
    work = data.copy()
    supported = {"tr.f.totrevenue", "tr.f.grossprofindproptot", "tr.f.cogstot", "tr.costofrevenuetotal"}
    work = work.loc[work.field.str.lower().isin(supported)].copy()
    work["period_end"] = pd.to_datetime(work.period_end, errors="coerce")
    work["numeric_value"] = pd.to_numeric(work.numeric_value, errors="coerce")
    work = work.loc[work.period_end.notna() & work.numeric_value.abs().lt(float("inf"))
                    & work.currency_requested.eq("USD") & work.reporting_state_requested.eq("Orig")]
    gross_keys = work.loc[work.field.str.lower().eq("tr.f.grossprofindproptot"), ["ticker", "ric", "period_end"]].drop_duplicates()
    work = work.merge(gross_keys, on=["ticker", "ric", "period_end"], how="inner")
    outputs = []
    for (ticker, ric, date), group in work.groupby(["ticker", "ric", "period_end"], sort=False):
        def unique_value(field):
            rows = group.loc[group.field.str.lower().eq(field)]
            values = rows.numeric_value.drop_duplicates()
            return (float(values.iloc[0]), rows.request_key.iloc[0]) if len(values) == 1 else None
        revenue = unique_value("tr.f.totrevenue")
        gross = unique_value("tr.f.grossprofindproptot")
        if revenue and gross:
            value = revenue[0] - gross[0]
            # Document the consistency check where the source also supplies COGS.
            costs = [unique_value(field) for field in ("tr.f.cogstot", "tr.costofrevenuetotal")]
            direct = next((v[0] for v in costs if v is not None), None)
            agrees = None if direct is None else math.isclose(value, direct, rel_tol=1e-6, abs_tol=1.)
            outputs.append({"ticker": ticker, "ric": ric, "period_end": date.date().isoformat(),
                            "target_metric": "cost_of_sales_provider", "formula": "TR.F.TotRevenue - TR.F.GrossProfIndPropTot",
                            "numeric_value": value, "input_request_keys": revenue[1] + "|" + gross[1],
                            "direct_source_value": direct, "agrees_with_direct_source": agrees,
                            "status": "RECONSTRUCTION_REVIEW" if value >= 0 else "NEGATIVE_RECONSTRUCTION_REVIEW",
                            "currency_requested": "USD", "reporting_state_requested": "Orig", "definition_review_required": True})
    return pd.DataFrame(outputs, columns=["ticker", "ric", "period_end", "target_metric", "formula", "numeric_value",
        "input_request_keys", "direct_source_value", "agrees_with_direct_source", "status", "currency_requested",
        "reporting_state_requested", "definition_review_required"])


def strict_market_plan(companies, data, blocked):
    adjusted = data.copy()
    iscap = adjusted.metric.eq("market_cap")
    dates = pd.to_datetime(adjusted.observation_date, errors="coerce")
    expected = dates.dt.to_period("M").astype(str).map(MONTH_ENDS)
    expected = pd.to_datetime(expected, errors="coerce")
    valid = dates.ge(expected) & dates.le(dates + pd.offsets.MonthEnd(0))
    adjusted = adjusted.loc[~iscap | valid]
    # Reuse batching/range logic after applying the audit's stricter date rule.
    return market_jobs(companies, adjusted, blocked)


def identity_review_jobs(client, universe, companies, blocked, original, source, root):
    """Investigate unresolved IDs, including conflicts, instead of only logging."""
    wanted = set(universe.ticker) - set(companies.ticker) | set(blocked)
    all_records = defaultdict(list)
    paths = [original / "identifier_search.json", source / "identifier_search.json", root / "identifier_search.json"]
    for path in paths:
        if path.exists():
            for ticker, item in json.loads(path.read_text(encoding="utf-8")).items():
                if ticker in wanted:
                    all_records[ticker].extend(item.get("records", []))
    identities, mappings = [], []
    client.start_phase("IDENTITY AND ISIN INVESTIGATION", 0)
    for company in universe.loc[universe.ticker.isin(wanted)].to_dict("records"):
        ticker = company["ticker"]
        existing = companies.loc[companies.ticker.eq(ticker)]
        expected = existing.iloc[0].get("isin", "") if not existing.empty else company.get("isin", "")
        # This is the same proven stock search; ISIN is a query, not a guessed RIC.
        if expected:
            try:
                found = client.ld.discovery.search(view=client.ld.discovery.Views.EQUITY_QUOTES, query=expected,
                    filter="BusinessEntity eq 'QUOTExEQUITY' and ExchangeCountry eq 'USA'",
                    select="RIC,DocumentTitle,ISIN,IssueISIN,IssueDate,RetireDate,IsPrimaryIssueRIC", top=100)
                if found is not None and not found.empty:
                    all_records[ticker].extend(json.loads(found.to_json(orient="records", date_format="iso")))
            except Exception as error:
                identities.append({"ticker": ticker, "status": "ISIN_SEARCH_ERROR", "error": str(error)})
        candidates = {}
        for item in all_records[ticker]:
            ric = item.get("RIC")
            isin = item.get("ISIN") or item.get("IssueISIN") or ""
            if not ric or not (name_matches(company.get("company", ""), item.get("DocumentTitle", "")) or (expected and isin == expected)):
                continue
            issued, retired = iso_date(item.get("IssueDate")), iso_date(item.get("RetireDate"))
            if (issued and company.get("last_membership_date") and issued > company["last_membership_date"]) or (retired and company.get("first_membership_date") and retired < company["first_membership_date"]):
                continue
            # One venue quote per security; different ISINs remain separate.
            group = isin or ric
            priority = (str(item.get("IsPrimaryIssueRIC", "")).lower() != "true", len(ric), ric)
            if group not in candidates or priority < candidates[group][0]:
                candidates[group] = (priority, item)
        if not existing.empty:
            row = existing.iloc[0].to_dict()
            candidates.setdefault("existing_ric_review", ((True, len(row["ric"]), row["ric"]),
                {"RIC": row["ric"], "ISIN": "", "DocumentTitle": row.get("company", "")}))
        seen = set()
        for _, candidate in candidates.values():
            ric = candidate["RIC"]
            if ric in seen:
                continue
            seen.add(ric)
            client.total += 1
            frame, key, entry = client.call([ric], ["TR.CommonName", "TR.ISIN"], {}, f"{ticker}: identity {ric}")
            identities.append({"ticker": ticker, "ric": ric, "expected_isin": expected,
                               "candidate_company": candidate.get("DocumentTitle", ""),
                               "status": "IDENTITY_REVIEW", "request_key": key,
                               "returned_identity_json": frame.to_json(orient="records")})
            mappings.append({**company, "ric": ric, "mapping_status": "IDENTITY_REVIEW_NOT_APPROVED"})
        print(f"Identity investigation {ticker}: {len(seen)} candidate securities", flush=True)
    save_text(root / "identity_investigation.csv", pd.DataFrame(identities).to_csv(index=False))
    return pd.DataFrame(mappings)


def save_completion(root, baseline, original_rows, rows, identity_rows, templates, gaps, companies, blocked, client, finished):
    print("Saving source candidates, reconstructions and recovery reports...", flush=True)
    observations = pd.DataFrame(rows, columns=OBS_COLUMNS + EXTRA_COLUMNS)
    primary = pd.DataFrame(original_rows, columns=OBS_COLUMNS + EXTRA_COLUMNS)
    candidates = pd.concat([primary, observations], ignore_index=True)
    save_text(root / "observations.csv", candidates.to_csv(index=False))
    save_text(root / "identity_candidate_observations.csv", pd.DataFrame(identity_rows, columns=OBS_COLUMNS + EXTRA_COLUMNS).to_csv(index=False))
    save_text(root / "statement_rows.csv", pd.DataFrame(templates).to_csv(index=False))
    if templates:
        definitions = pd.DataFrame(templates)[["provider_field", "provider_description", "target_metric", "statement"]].drop_duplicates()
        save_text(root / "field_definitions.csv", definitions.to_csv(index=False))
    all_values = pd.concat([baseline, candidates], ignore_index=True)
    subset = ["ticker", "ric", "metric", "field", "period_end", "observation_date", "numeric_value", "announcement_date", "requested_fiscal_year"]
    all_values = all_values.drop_duplicates(subset=subset)
    save_text(root / "combined_observations_candidate.csv", all_values.to_csv(index=False))
    derived = reconstruction_candidates(all_values)
    save_text(root / "derived_cost_candidates.csv", derived.to_csv(index=False))
    available = observed_keys(normalize_candidates(all_values))
    outcomes = gaps.copy()
    outcomes["source_candidate_found"] = [(r.ticker, r.ric, r.metric, r.required_calendar_year) in available for r in outcomes.itertuples()]
    catalog_keys = {(r["ticker"], r["ric"], r["requested_fiscal_year"]) for r in templates}
    outcomes["returned_statement_template"] = [(r.ticker, r.ric, r.request_fiscal_year) in catalog_keys for r in outcomes.itertuples()]
    save_text(root / "gap_outcomes.csv", outcomes.to_csv(index=False))
    logs = pd.DataFrame(client.logs) if client else pd.DataFrame()
    if not logs.empty:
        save_text(root / "request_report.csv", logs.to_csv(index=False))
        fronts = logs.groupby("phase").agg(request_jobs=("status", "size"), sdk_requests=("source", lambda s: int(s.eq("SDK").sum())),
                                             request_errors=("status", lambda s: int(s.eq("REQUEST_ERROR").sum())),
                                             empty_tables=("status", lambda s: int(s.eq("EMPTY_RESPONSE").sum())))
        save_text(root / "fronts_report.csv", fronts.to_csv())
    lines = ["# All-fronts LSEG completion", "", f"- Version: `{VERSION}`", f"- Finished plan: {finished}",
             f"- Mapped historical ticker labels: {len(companies)}", f"- Missing candidate company-years before: {len(gaps)}",
             f"- Candidate company-years found: {int(outcomes.source_candidate_found.sum())}",
             f"- New primary-field observations: {len(primary)}", f"- Additional source candidates: {len(observations)}",
             f"- Separate identity-review observations: {len(identity_rows)}", f"- Returned template rows: {len(templates)}",
             f"- Derived COGS candidates (not source observations): {len(derived)}",
             f"- Identity conflicts remain unapproved: {', '.join(sorted(blocked)) or 'none'}", "",
             "## Fronts", "", "Identifiers and ISINs: identifier_recovery.csv, identity_investigation.csv, identity_candidate_observations.csv.",
             "Annual amounts: annual_gap_plan.csv, observations.csv, gap_outcomes.csv.",
             "Whole statements and industry-specific definitions: template_capabilities.csv, statement_rows.csv, field_definitions.csv.",
             "Publication-period issues: publication_review_before.csv, publication_review_after.csv. Adjacent FY labels are queried; Orig is kept.",
             "Reconstruction: derived_cost_candidates.csv; requested currency/state and exact period must match; conflicts prevent calculation.",
             "Month-end capitalization: strict_market_plan.csv, using the embedded project trading calendar, without seven-day tolerance.",
             "Requests, errors and cache sources: fronts_report.csv, request_report.csv, recovery_raw.sqlite.", "",
             "## Interpretation", "", "No percentage of FF eligibility is inferred from response counts. Missing expenses are not zero.",
             "A numeric alternative, gross-profit calculation, or unchanged current identity is not an approved historical FF input.",
             "No template date is fabricated from its FY label. Discovered fields are separately requested with their own period dates.",
             "Late publication remains a limitation when no timely original is returned; no unsupported as-of parameter or restated fallback is invented.",
             "When whole templates are unavailable, template_capabilities.csv records the attempted requests; documented direct fields still run.",
             "Financial/industry templates provide context, not proof that an absent COGS entry is zero or not applicable.",
             "Identity-review observations and calculated candidates are excluded from combined_observations_candidate.csv.",
             "All input folders are read-only. Re-run the same command to resume; --retry-empty rechecks empty replies."]
    save_text(root / "report.md", "\n".join(lines) + "\n")


def run(args):
    original = (args.original or locate_input("lseg_company_data_output")).resolve()
    source = (args.source or locate_input("lseg_company_recovery_output")).resolve()
    root = args.output.resolve()
    for folder in (original, source):
        if root == folder or root in folder.parents or folder in root.parents:
            raise ValueError("Output must be a separate non-nested directory; input files remain read-only.")
    universe = read_csv(original / "requested_universe.csv")
    companies = read_csv(source / "selected_companies.csv")
    baseline = pd.read_csv(source / "combined_observations_candidate.csv", low_memory=False)
    alternatives = pd.read_csv(source / "alternative_observations.csv", low_memory=False)
    baseline = pd.concat([baseline, alternatives], ignore_index=True)
    root.mkdir(parents=True, exist_ok=True)
    print(f"LSEG COMPANY COMPLETION {VERSION}\nScript: {Path(__file__).resolve()}\nPython: {sys.executable}\nOriginal: {original}\nPrevious recovery: {source}\nOutput: {root}", flush=True)
    ld, client = None, None
    rows, original_rows, identity_rows, templates = [], [], [], []
    gaps = pd.DataFrame(columns=["ticker", "ric", "metric", "required_calendar_year", "request_fiscal_year", "fiscal_label_shift"])
    blocked = set()
    finished = False
    try:
        if not args.plan_only:
            import lseg.data as ld
            if "header_type" not in inspect.signature(ld.get_data).parameters:
                raise RuntimeError("Use the verified Python 3.12 / lseg-data 2.1.1 environment.")
            ld.open_session()
            print("Connection check: known CELG FY2018 revenue request.", flush=True)
            probe = ld.get_data(universe=["CELG.O^K19"], fields=["TR.TotalRevenue"], parameters={"Period": "FY2018"})
            print(probe, flush=True)
            if probe is None or probe.empty:
                raise RuntimeError("Previously successful connection check returned no rows.")
            values = probe.drop(columns=[c for c in probe if str(c).lower() == "instrument"], errors="ignore")
            if not values.apply(pd.to_numeric, errors="coerce").notna().any().any():
                raise RuntimeError("Connection check has no numeric revenue.")
        companies, blocked = resolve_companies(ld, universe, companies, original, root, args.approved_mapping)
        invalid_period = (pd.to_datetime(companies.first_membership_date, errors="coerce").isna()
                          | pd.to_datetime(companies.last_membership_date, errors="coerce").isna())
        save_text(root / "no_membership_period_review.csv", companies.loc[invalid_period].to_csv(index=False))
        save_text(root / "requested_universe.csv", universe.to_csv(index=False))
        normalized = normalize_candidates(baseline)
        gaps = build_gaps(companies, normalized, blocked)
        timing, timing_jobs = publication_plan(companies, baseline, gaps, blocked)
        caps = strict_market_plan(companies, baseline, blocked)
        save_text(root / "annual_gap_plan.csv", gaps.to_csv(index=False))
        save_text(root / "publication_review_before.csv", timing.to_csv(index=False))
        save_text(root / "strict_market_plan.csv", pd.DataFrame([{"start": a, "end": b, "tickers": "|".join(c.ticker)} for a,b,c in caps]).to_csv(index=False))
        print(f"Remaining source-candidate gaps: {len(gaps)} company-years; timing requests: {len(timing_jobs)}; precise market-cap jobs: {len(caps)}.", flush=True)
        if args.plan_only:
            print("Offline plans saved. No Workspace session or online extraction.", flush=True)
            return
        client = Client(ld, root, args.retry_empty)
        seed_response_cache(client, [original, source])
        review_companies = identity_review_jobs(client, universe, companies, blocked, original, source, root)
        if not review_companies.empty:
            review_gaps = build_gaps(review_companies, pd.DataFrame(columns=OBS_COLUMNS), set())
            recover_annual(client, annual_jobs(review_gaps), "IDENTITY REVIEW FINANCIALS", collected=identity_rows)
            review_caps = strict_market_plan(review_companies, pd.DataFrame(columns=OBS_COLUMNS), set())
            client.start_phase("IDENTITY REVIEW MARKET CAP", len(review_caps))
            for start, end, pairs in review_caps:
                table, key, entry = client.call(pairs.ric, ["TR.CompanyMarketCap", "TR.CompanyMarketCap.date"],
                    {"SDate": start, "EDate": end, "Frq": "M", "Curn": "USD", "Scale": 0},
                    f"Review-only capitalization {start} to {end}, {len(pairs)} labels")
                if not table.empty:
                    parsed, _ = parse_observations(table, pairs, "market_cap", "TR.CompanyMarketCap", "date", "number", None, key)
                    for row in parsed:
                        row.update({"target_metric": "market_cap", "definition_review_required": True, "recovery_stage": "IDENTITY REVIEW MARKET CAP"})
                    identity_rows.extend(parsed)
        # Original fields are retried only for remaining gaps; cached replies are reused.
        recover_annual(client, annual_jobs(gaps), "REMAINING ORIGINAL FIELDS", collected=original_rows)
        execute_fields(client, timing_jobs, "PUBLICATION PERIOD RECONCILIATION", rows)
        extra_specs = {**NEW_FIELDS}
        # Both inputs for a gross-profit reconstruction are requested for missing COGS.
        extra_specs["cost_of_sales_provider"] = NEW_FIELDS["cost_of_sales_provider"] + NEW_FIELDS["gross_profit_provider"] + NEW_FIELDS["revenue_for_reconstruction"]
        direct_jobs = batch_specs(gaps, extra_specs)
        # Retain the actual role of each field rather than labelling gross profit as COGS.
        direct_jobs = [(y, "gross_profit_provider" if f.lower() == "tr.f.grossprofindproptot" else "revenue" if f.lower() == "tr.f.totrevenue" else target, f, prop, kind, pairs)
                       for y,target,f,prop,kind,pairs in direct_jobs]
        execute_fields(client, direct_jobs, "DOCUMENTED EXTRA FIELDS AND GROSS PROFIT", rows)
        collect_templates(client, gaps, timing, templates)
        execute_fields(client, discovered_jobs(templates, baseline, rows), "PROVIDER-DISCOVERED INDUSTRY FIELDS", rows)
        client.start_phase("PRECISE MONTH-END MARKET CAP", len(caps))
        for start, end, pairs in caps:
            table, key, entry = client.call(pairs.ric, ["TR.CompanyMarketCap", "TR.CompanyMarketCap.date"],
                {"SDate": start, "EDate": end, "Frq": "M", "Curn": "USD", "Scale": 0}, f"{start} to {end}, {len(pairs)} labels")
            if not table.empty:
                parsed, _ = parse_observations(table, pairs, "market_cap", "TR.CompanyMarketCap", "date", "number", None, key)
                for row in parsed:
                    row.update({"target_metric": "market_cap", "definition_review_required": False, "recovery_stage": "PRECISE MONTH-END MARKET CAP"})
                original_rows.extend(parsed)
        updated = pd.concat([baseline, pd.DataFrame(original_rows), pd.DataFrame(rows)], ignore_index=True)
        remaining_timing, _ = publication_plan(companies, updated, gaps.iloc[:0], blocked)
        save_text(root / "publication_review_after.csv", remaining_timing.to_csv(index=False))
        finished = True
    finally:
        if client is not None:
            try:
                save_completion(root, baseline, original_rows, rows, identity_rows, templates, gaps, companies, blocked, client, finished)
            finally:
                client.db.close()
        if ld is not None:
            try:
                ld.close_session()
            except Exception as error:
                print(f"Session close warning: {error}", flush=True)
    print(f"Finished. Read {root / 'report.md'}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "lseg_company_completion_output")
    parser.add_argument("--approved-mapping", type=Path)
    parser.add_argument("--retry-empty", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    try:
        run(parser.parse_args())
    except KeyboardInterrupt:
        print("\nInterrupted. Raw responses are checkpointed; re-run to resume.", flush=True)
        raise SystemExit(130)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
