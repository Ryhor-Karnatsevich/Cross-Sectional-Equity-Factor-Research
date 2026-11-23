"""Recover missing LSEG company inputs without overwriting the first extraction.

Copy this ONE file beside lseg_company_data.py on the Workspace computer.
Keep the previous lseg_company_data_output directory there, then run:
    py -3.12 lseg_company_recovery.py

Default: all unresolved identities and missing required company-years/months.
Uses the successful ld.get_data / Period=FY2018 / Orig / USD / Scale=0 interface.
No price downloads, model calculation or main-project pipeline changes.

Inputs: lseg_company_data_output beside this file (or --source PATH).
Outputs: lseg_company_recovery_output beside this file (or --output PATH).
Successful and empty responses are checkpointed. Failed requests are retried on
next run. --retry-empty rechecks completed empty responses, not successful ones.
--plan-only creates the offline recovery plan without opening Workspace.
--approved-mapping CSV accepts explicitly approved ticker,ric,isin,approved rows.

Alternative accounting fields are saved separately as definition-review candidates.
They never replace original metrics automatically. No missing-to-zero filling.
Dates/publication and company identity still require review before modelling.

Primary field references:
https://community.developers.lseg.com/discussion/90580
https://community.developers.lseg.com/discussion/73149
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

VERSION = "2026-11-17-targeted-recovery-v1"
BATCH_SIZE = 20

# These definitions/helpers are copied from the previously successful downloader.
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


# -------------------------
# RECOVERY SETTINGS
PRIMARY_METRICS = ("total_assets", "common_equity_provider", "revenue",
                   "cost_of_sales_provider", "sga", "interest_expense_provider",
                   "balance_announcement", "income_announcement")
# Documented fields, not assumed equivalent accounting definitions. Each result
# keeps its actual field code and goes ONLY to alternative_observations.csv.
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


def load_inputs(source):
    required = ["requested_universe.csv", "selected_companies.csv", "observations.csv"]
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing {missing} in {source}. Keep the previous output folder beside this script or use --source PATH.")
    universe = read_csv(source / "requested_universe.csv")
    selected = read_csv(source / "selected_companies.csv")
    observations = pd.read_csv(source / "observations.csv", low_memory=False)
    if universe.ticker.duplicated().any() or selected.ticker.duplicated().any():
        raise ValueError("Multiple mappings per ticker in input; resolve these before recovery.")
    needed = {"ticker", "metric", "period_end", "numeric_value", "announcement_date", "ric"}
    if not needed.issubset(observations.columns):
        raise ValueError(f"Unexpected observations columns; missing {needed - set(observations.columns)}")
    return universe, selected, observations


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


def write_outputs(root, baseline, rows, alternatives, initial_gaps, companies, completed, started):
    repaired = pd.DataFrame(rows, columns=OBS_COLUMNS + EXTRA_COLUMNS)
    alternate = pd.DataFrame(alternatives, columns=OBS_COLUMNS + EXTRA_COLUMNS)
    save_text(root / "observations.csv", repaired.to_csv(index=False))
    save_text(root / "alternative_observations.csv", alternate.to_csv(index=False))
    combined = pd.concat([baseline, repaired], ignore_index=True)
    subset = ["ticker", "ric", "metric", "field", "period_end", "observation_date", "numeric_value", "announcement_date", "requested_fiscal_year"]
    combined = combined.drop_duplicates(subset=subset)
    save_text(root / "combined_observations_candidate.csv", combined.to_csv(index=False))
    present = observed_keys(combined)
    outcomes = initial_gaps.copy()
    outcomes["original_metric_recovered"] = [
        (r.ticker, r.ric, r.metric, r.required_calendar_year) in present for r in outcomes.itertuples()]
    alt_keys = set()
    if not alternate.empty:
        alt_view = alternate.copy()
        alt_view["metric"] = alt_view.target_metric
        alt_keys = observed_keys(alt_view)
    outcomes["alternative_candidate_found"] = [
        (r.ticker, r.ric, r.metric, r.required_calendar_year) in alt_keys for r in outcomes.itertuples()]
    save_text(root / "gap_outcomes.csv", outcomes.to_csv(index=False))
    summary = outcomes.groupby("metric").agg(missing_before=("ticker", "size"),
                                              recovered_original=("original_metric_recovered", "sum"),
                                              alternative_candidates=("alternative_candidate_found", "sum"))
    summary["still_missing_original"] = summary.missing_before - summary.recovered_original
    save_text(root / "gap_summary.csv", summary.to_csv())
    lines = ["# Targeted LSEG company-data recovery", "", f"- Version: `{VERSION}`",
             f"- Finished extraction plan: {completed}", f"- Elapsed: {duration(time.perf_counter() - started)}",
             f"- Selected ticker mappings: {len(companies)}", f"- New source observations: {len(repaired)}",
             f"- Alternative definition-review observations: {len(alternate)}", "",
             "| Metric | Missing company-years before | Recovered original field | Alternative candidates | Still missing original |",
             "|---|---:|---:|---:|---:|"]
    for metric, row in summary.iterrows():
        lines.append(f"| {metric} | {row.missing_before} | {row.recovered_original} | {row.alternative_candidates} | {row.still_missing_original} |")
    lines += ["", "Counts are required company-years within historical membership spans, not the membership-day percentages in the earlier audit.",
              "Newly resolved company mappings are still extraction candidates. No generic equity, revenue or expense definitions are automatically equated.",
              "Existing source files are unchanged. combined_observations_candidate.csv is a separate copy containing original fields only.",
              "alternative_observations.csv is excluded from that combined file and all original-field recovery counts.",
              "Publication dates are retained, not fabricated. A recovered amount does not establish timely availability or exact FF eligibility.",
              "Some fiscal-year labels end in the following calendar year. Observed label/date offsets are recorded in annual_gap_plan.csv.",
              "Known ISIN mismatches remain blocked unless explicitly supplied in --approved-mapping.",
              "Reused or ambiguous tickers are listed in identifier_recovery.csv; no arbitrary first search result is accepted.",
              "Market-cap values retain their returned dates; no missing month is filled from an older observation.",
              "Successful and empty raw responses are saved in recovery_raw.sqlite. Repeat the command to resume; --retry-empty rechecks empty responses."]
    save_text(root / "report.md", "\n".join(lines) + "\n")


def run(args):
    source, root = args.source.resolve(), args.output.resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Source and recovery output must be separate, non-nested directories.")
    universe, selected, baseline = load_inputs(source)
    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print(f"LSEG COMPANY RECOVERY {VERSION}\nScript: {Path(__file__).resolve()}\nPython: {sys.executable}", flush=True)
    print(f"Source (read only): {source}\nRecovery output: {root}\nAll {len(universe)} original tickers considered; only gaps are requested.", flush=True)
    ld, client = None, None
    rows, alternatives = [], []
    gaps = pd.DataFrame()
    companies = selected
    completed = False
    try:
        if not args.plan_only:
            import lseg.data as ld
            print(f"LSEG library: {getattr(ld, '__version__', 'unknown')}\nOpening signed-in Workspace session...", flush=True)
            if "header_type" not in inspect.signature(ld.get_data).parameters:
                raise RuntimeError("Use the working lseg-data 2.1.1 Python environment: py -3.12 ...")
            ld.open_session()
            print("Connection check: the same CELG revenue FY2018 request.", flush=True)
            check = ld.get_data(universe=["CELG.O^K19"], fields=["TR.TotalRevenue"], parameters={"Period": "FY2018"})
            print(check, flush=True)
            if not isinstance(check, pd.DataFrame) or check.empty:
                raise RuntimeError("Connection check returned no rows; stopping before recovery.")
            values = check.drop(columns=[c for c in check if str(c).lower() == "instrument"], errors="ignore")
            if not values.apply(pd.to_numeric, errors="coerce").notna().any().any():
                raise RuntimeError("Connection check returned no numeric revenue.")
        companies, blocked = resolve_companies(ld, universe, selected, source, root, args.approved_mapping)
        invalid_period = (pd.to_datetime(companies.first_membership_date, errors="coerce").isna()
                          | pd.to_datetime(companies.last_membership_date, errors="coerce").isna())
        save_text(root / "no_membership_period_review.csv", companies.loc[invalid_period].to_csv(index=False))
        gaps = build_gaps(companies, baseline, blocked)
        save_text(root / "annual_gap_plan.csv", gaps.to_csv(index=False))
        jobs = annual_jobs(gaps)
        cap_jobs = market_jobs(companies, baseline, blocked)
        print(f"Plan: {len(gaps)} missing original company-years; {len(jobs)} annual jobs; {len(cap_jobs)} monthly-capitalization jobs.", flush=True)
        print(f"Identity mismatch tickers held for review: {', '.join(sorted(blocked)) or 'none'}", flush=True)
        if args.plan_only:
            print("Offline plan written. No LSEG requests were sent.", flush=True)
            return
        client = Client(ld, root, args.retry_empty)
        recover_annual(client, jobs, "ORIGINAL FIELDS", collected=rows)
        write_outputs(root, baseline, rows, alternatives, gaps, companies, False, started)
        now = pd.concat([baseline, pd.DataFrame(rows, columns=OBS_COLUMNS + EXTRA_COLUMNS)], ignore_index=True)
        remaining = build_gaps(companies, now, blocked)
        alternative_gaps = remaining.loc[remaining.metric.isin(ALTERNATIVES)]
        recover_annual(client, annual_jobs(alternative_gaps), "DOCUMENTED ALTERNATIVE FIELDS", alternatives=True, collected=alternatives)
        write_outputs(root, baseline, rows, alternatives, gaps, companies, False, started)
        client.start_phase("MONTHLY MARKET CAP", len(cap_jobs))
        for start, end, pairs in cap_jobs:
            frame, key, entry = client.call(pairs.ric, ["TR.CompanyMarketCap", "TR.CompanyMarketCap.date"],
                                            {"SDate": start, "EDate": end, "Frq": "M", "Curn": "USD", "Scale": 0},
                                            f"{start} to {end}, {len(pairs)} tickers")
            if not frame.empty:
                recovered, status = parse_observations(frame, pairs, "market_cap", "TR.CompanyMarketCap", "date", "number", None, key)
                for row in recovered:
                    row.update({"target_metric": "market_cap", "definition_review_required": False, "recovery_stage": "MONTHLY MARKET CAP"})
                rows.extend(recovered)
        completed = True
    finally:
        if not args.plan_only and client:
            try:
                write_outputs(root, baseline, rows, alternatives, gaps, companies, completed, started)
            finally:
                client.db.close()
        if ld is not None:
            try:
                ld.close_session()
            except Exception as error:
                print(f"Session close warning: {type(error).__name__}: {error}", flush=True)
    print(f"Finished in {duration(time.perf_counter() - started)}. Read {root / 'report.md'}", flush=True)


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=here / "lseg_company_data_output")
    parser.add_argument("--output", type=Path, default=here / "lseg_company_recovery_output")
    parser.add_argument("--approved-mapping", type=Path)
    parser.add_argument("--retry-empty", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nInterrupted. Completed requests are saved; repeat the same command to resume.", flush=True)
        raise SystemExit(130)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
