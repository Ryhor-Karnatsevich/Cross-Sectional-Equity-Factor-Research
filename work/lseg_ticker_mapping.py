"""Run on the university PC with LSEG Workspace open and signed in.

Run normally: python lseg_ticker_mapping.py
All 269 missing-price tickers and membership periods are embedded below.
Produces ONE CSV beside this script. No additional input files are required.

Only discovers candidate securities. Never selects/merges price histories.
Requires: pip install lseg-data pandas
"""
import argparse
from pathlib import Path
import re
import time

import pandas as pd
import lseg.data as ld
from lseg.data.content import search as search_content


# Snapshot of actual missing membership prices in the project dataset.
# Format: historical ticker,first membership date,last membership date.
DEFAULT_REQUEST_TEXT = """
AABA,2008-01-02,2017-06-16
ABI,2008-01-02,2008-11-21
ABKFQ,2008-01-02,2008-06-10
ABMD,2018-05-31,2022-12-21
ACAS,2008-01-02,2009-03-03
ACS,2008-01-02,2010-02-05
ADT,2012-10-02,2016-04-29
AGN,2008-01-02,2020-05-11
AKS,2008-07-01,2011-12-16
ALTR,2008-01-02,2015-12-24
ALXN,2012-05-25,2021-07-20
ANDV,2008-01-02,2018-09-28
ANRZQ,2011-06-02,2012-10-01
ANSS,2017-06-19,2025-07-17
APC,2008-01-02,2019-08-08
APOL,2008-01-02,2013-06-28
ARG,2009-09-09,2016-05-20
ARNC,2008-01-02,2020-04-03
ATGE,2009-06-09,2012-09-28
ATVI,2015-08-31,2023-10-17
AVB,2008-01-02,2026-08-17
AVP,2008-01-02,2015-03-20
AW,2008-01-02,2008-12-04
AYE,2008-01-02,2011-02-25
BBBY,2008-01-02,2017-07-25
BCR,2008-01-02,2017-12-28
BDK,2008-01-02,2010-03-12
BEAM,2008-01-02,2014-04-30
BHGE,2008-01-02,2019-10-17
BIG,2008-01-02,2013-02-13
BJS,2008-01-02,2010-04-28
BK,2008-01-02,2026-05-20
BMC,2008-01-02,2013-09-10
BNI,2008-01-02,2010-02-12
BRCM,2008-01-02,2016-01-29
BRL,2008-01-02,2008-12-22
BSC,2008-01-02,2008-05-30
BTUUQ,2008-01-02,2014-09-19
BUD,2008-01-02,2008-11-17
BXLT,2015-07-01,2016-06-02
CA,2008-01-02,2018-11-05
CAM,2008-01-29,2016-04-01
CBE,2008-01-02,2012-11-30
CBH,2008-01-02,2008-03-28
CBS,2008-01-02,2019-12-04
CCE,2008-01-02,2016-05-27
CCTYQ,2008-01-02,2008-03-28
CDAY,2021-09-20,2024-01-31
CEG,2008-01-02,2026-08-18
CELG,2008-01-02,2019-11-20
CEPH,2008-11-17,2011-10-13
CERN,2010-04-30,2022-06-07
CFC,2008-01-02,2008-06-30
CFN,2009-09-01,2015-03-16
CHK,2008-01-02,2018-03-16
CITGQ,2008-01-02,2009-07-24
CMA,2008-01-02,2024-06-21
CMCSK,2015-09-21,2015-12-11
COG,2008-06-23,2021-10-01
COL,2008-01-02,2018-11-26
COV,2008-01-02,2015-01-26
CPGX,2015-07-02,2016-06-30
CPWR,2008-01-02,2011-12-30
CSRA,2015-11-30,2018-04-03
CTLT,2020-09-21,2024-12-20
CTRA,2021-10-04,2026-05-06
CTX,2008-01-02,2009-08-18
CTXS,2008-01-02,2022-09-30
CVC,2010-12-20,2016-06-20
CVG,2008-01-02,2009-12-18
CVH,2008-01-02,2013-05-06
CXO,2016-02-22,2021-01-20
DAY,2024-02-01,2026-02-06
DELL,2008-01-02,2026-08-18
DF,2008-01-02,2013-05-23
DFS,2008-01-02,2025-05-16
DISCA,2010-03-01,2022-04-08
DISCK,2014-08-07,2022-04-08
DISH,2017-03-13,2023-06-16
DNB,2008-12-02,2017-04-04
DNR,2009-04-02,2015-03-20
DO,2009-02-26,2016-09-30
DOW,2008-01-02,2026-08-18
DRE,2017-07-26,2022-09-30
DTV,2008-01-02,2015-07-24
DWDP,2017-09-01,2019-05-31
DYN,2008-01-02,2009-12-18
EA,2008-01-02,2026-08-04
EDS,2008-01-02,2008-08-25
EKDKQ,2008-01-02,2010-12-17
EMC,2008-01-02,2016-09-06
ENDP,2015-01-27,2017-03-01
EP,2008-01-02,2012-05-24
EQ,2008-01-02,2009-06-30
EQR,2008-01-02,2026-08-17
ESRX,2008-01-02,2018-12-20
ESV,2008-01-02,2016-03-29
ETFC,2008-01-02,2020-10-06
EVHC,2016-12-02,2018-10-10
FDO,2008-01-02,2015-07-06
FI,2023-06-07,2025-11-10
FISV,2008-01-02,2026-08-18
FL,2016-04-04,2019-08-08
FLIR,2009-01-02,2021-05-13
FOX,2015-09-21,2026-08-18
FOXA,2008-01-02,2026-08-18
FRC,2019-01-02,2023-05-03
FRX,2008-01-02,2014-06-30
FTR,2008-01-02,2017-03-17
GAS,2008-01-02,2016-06-30
GENZ,2008-01-02,2011-04-01
GGP,2008-01-02,2018-08-27
GMCR,2014-03-24,2016-03-02
GPS,2008-01-02,2022-02-01
GR,2008-01-02,2012-07-26
HAR,2008-01-02,2017-03-10
HBI,2015-03-23,2021-12-17
HCBK,2008-01-02,2015-10-30
HCP,2008-03-31,2019-11-04
HES,2008-01-02,2025-07-22
HET,2008-01-02,2008-01-28
HFC,2018-06-18,2021-06-03
HNZ,2008-01-02,2013-06-06
HOLX,2016-03-30,2026-04-08
HOT,2008-01-02,2016-09-22
HPC,2008-01-02,2008-11-13
HRS,2008-09-22,2019-05-31
HSH,2008-01-02,2012-06-28
HSP,2008-01-02,2015-09-02
IAC,2008-01-02,2008-08-20
IGT,2008-01-02,2014-06-19
INFO,2017-06-02,2022-03-01
IPG,2008-01-02,2025-11-26
IR,2008-01-02,2026-08-18
JAVA,2008-01-02,2010-01-26
JCP,2008-01-02,2013-11-29
JEC,2008-01-02,2019-12-09
JNPR,2008-01-02,2025-07-08
JNS,2008-01-02,2011-11-22
JNY,2008-01-02,2009-03-03
JOY,2011-02-28,2015-10-07
JWN,2008-01-02,2020-06-19
K,2008-01-02,2025-12-10
KATE,2008-01-02,2008-12-01
KG,2008-01-02,2010-12-17
KRFT,2012-10-02,2015-07-02
KSU,2013-05-24,2021-12-13
LB,2008-01-02,2021-08-02
LEG,2008-01-02,2021-12-17
LEHMQ,2008-01-02,2008-09-16
LIFE,2008-11-24,2014-01-23
LLL,2008-01-02,2019-06-28
LLTC,2008-01-02,2017-03-10
LM,2008-01-02,2016-12-01
LO,2008-06-11,2015-06-11
LSI,2008-01-02,2014-05-06
LVLT,2014-11-05,2017-10-12
LXK,2008-01-02,2012-09-28
MDP,2008-01-02,2011-01-03
MEE,2008-06-23,2011-06-01
MER,2008-01-02,2008-12-31
MFE,2008-12-23,2011-02-28
MHS,2008-01-02,2012-03-30
MI,2008-01-02,2011-07-05
MIL,2008-01-02,2010-07-14
MJN,2009-12-21,2017-06-14
MMC,2008-01-02,2026-01-13
MMI,2011-01-04,2012-05-21
MNK,2014-08-19,2017-07-25
MON,2008-01-02,2018-06-06
MRO,2008-01-02,2024-11-25
MTLQQ,2008-01-02,2009-06-02
MWV,2008-01-02,2015-07-01
MWW,2008-01-02,2011-12-16
MXIM,2018-12-03,2021-08-27
MYL,2008-01-02,2020-11-16
NBL,2008-01-02,2020-10-09
NCC,2008-01-02,2008-12-31
NE,2008-01-02,2015-07-17
NFX,2010-12-20,2019-02-14
NLSN,2013-07-09,2022-10-11
NOVL,2008-01-02,2011-04-27
NSM,2008-01-02,2011-09-23
NVLS,2008-01-02,2012-06-04
NYX,2008-01-02,2013-11-12
ODP,2008-01-02,2010-12-17
OMX,2008-01-02,2008-06-20
PARA,2022-02-17,2025-08-07
PBCT,2008-11-13,2022-04-01
PBG,2008-01-02,2010-02-26
PCL,2008-01-02,2016-02-19
PCP,2008-01-02,2016-01-29
PDCO,2008-01-02,2018-03-16
PEAK,2019-11-05,2024-03-01
PETM,2012-10-05,2015-03-11
PGN,2008-01-02,2012-06-29
PLL,2008-01-02,2015-08-28
POM,2008-01-02,2016-03-23
PTV,2008-01-02,2010-11-16
PX,2008-01-02,2018-10-30
PXD,2008-09-24,2024-05-07
Q,2008-01-02,2026-08-18
QEP,2010-07-01,2015-06-30
QLGC,2008-01-02,2011-01-14
RAI,2008-01-02,2017-07-24
RDC,2008-01-02,2014-08-18
RE,2017-06-19,2023-07-07
RHT,2009-07-27,2019-07-12
ROH,2008-01-02,2009-04-01
RRD,2008-01-02,2012-12-11
RSHCQ,2008-01-02,2011-06-30
RTN,2008-01-02,2020-04-03
RX,2008-01-02,2010-02-25
S,2008-01-02,2013-07-08
SAF,2008-01-02,2008-09-22
SATS,2026-03-23,2026-06-23
SBNY,2021-12-20,2023-03-14
SCG,2009-01-02,2018-12-31
SE,2008-01-02,2017-02-24
SEE,2008-01-02,2023-12-15
SGP,2008-01-02,2009-11-03
SHLD,2008-01-02,2012-09-04
SIAL,2008-01-02,2015-11-17
SII,2008-01-02,2010-08-26
SIVB,2018-03-19,2023-03-14
SNDK,2008-01-02,2026-08-18
SNI,2008-07-01,2018-03-06
SOV,2008-01-02,2009-01-29
SPLS,2008-01-02,2017-09-12
SRCL,2008-11-19,2018-11-30
STI,2008-01-02,2019-12-06
STJ,2008-01-02,2017-01-04
STR,2008-01-02,2010-06-30
SUN,2008-01-02,2012-10-04
SUNEQ,2008-01-02,2011-12-16
SWN,2008-06-06,2017-04-03
SWY,2008-01-02,2015-01-26
TE,2008-01-02,2016-06-30
TEG,2008-01-02,2015-06-29
TGNA,2008-01-02,2017-06-01
TIE,2008-01-02,2012-12-21
TIF,2008-01-02,2021-01-06
TSS,2008-01-02,2019-09-20
TWC,2009-03-30,2016-05-17
TWTR,2018-06-07,2022-10-31
TWX,2008-01-02,2018-06-14
UST,2008-01-02,2009-01-05
UTX,2008-01-02,2020-04-02
VAR,2008-01-02,2021-04-19
VIAB,2008-01-02,2019-12-04
VIAC,2019-12-05,2022-02-16
VLTO,2023-10-02,2026-08-18
WAMUQ,2008-01-02,2008-09-29
WB,2008-01-02,2008-12-31
WBA,2008-01-02,2025-08-27
WCG,2018-09-17,2020-01-27
WFM,2008-01-02,2017-08-25
WFT,2008-01-02,2009-02-25
WIN,2008-01-02,2015-04-06
WPX,2012-01-03,2014-03-21
WRK,2015-07-02,2024-07-05
WWY,2008-01-02,2008-10-06
WYE,2008-01-02,2009-10-15
WYND,2008-01-02,2018-05-30
X,2008-01-02,2014-07-01
XEC,2014-06-20,2020-03-02
XL,2008-01-02,2018-09-11
XLNX,2008-01-02,2022-02-14
XTO,2008-01-02,2010-06-25
"""
DEFAULT_REQUESTS = {
    ticker: (start, end)
    for ticker, start, end in (
        line.split(',') for line in DEFAULT_REQUEST_TEXT.strip().splitlines()
    )
}
DEFAULT_TICKERS = list(DEFAULT_REQUESTS)
# Search hints, NOT accepted security mappings.
NAME_HINTS = {
    'CELG': 'Celgene',
    'ATVI': 'Activision Blizzard',
    'TWTR': 'Twitter',
    'EMC': 'EMC Corp',
    'MER': 'Merrill Lynch',
    'BSC': 'Bear Stearns',
}
FIELDS = [
    'RIC', 'DocumentTitle', 'TickerSymbol', 'BusinessEntity',
    'ExchangeCountry', 'ExchangeName', 'ExchangeCode',
    'PermID', 'ISIN', 'IssueISIN', 'ListingStatus', 'AssetState',
    'RetireDate', 'IssueDate', 'IsPrimaryRIC', 'IsPrimaryIssueRIC',
    'RCSAssetCategoryLeaf',
]
OUTPUT_COLUMNS = [
    'ticker', 'status', 'company', 'ric', 'alternative_rics', 'isin',
    'quote_permid', 'exchange', 'asset_category', 'listing_status',
    'issue_date', 'retire_date', 'ticker_exact', 'period_check',
    'search_methods', 'security_candidate_count', 'quote_candidate_count',
    'capped_queries', 'error', 'approved', 'review_note',
    'requested_start', 'requested_end',
]
STOCK_CATEGORIES = ('Ordinary Share', 'American Depository Receipt', 'Depository Receipt')


def value(row, field):
    item = row.get(field)
    return '' if item is None or pd.isna(item) else str(item)


def literal(text):
    return str(text).replace("'", "''")


def normalized_ticker(text):
    return str(text).strip().upper().replace('-', '.')


def period_check(row, start, end):
    issued = pd.to_datetime(row.get('IssueDate'), errors='coerce', utc=True)
    retired = pd.to_datetime(row.get('RetireDate'), errors='coerce', utc=True)
    start = pd.Timestamp(start, tz='UTC')
    end = pd.Timestamp(end, tz='UTC')
    if (pd.notna(issued) and issued > end) or (pd.notna(retired) and retired < start):
        return 'outside_requested_period'
    if pd.notna(issued) and pd.notna(retired):
        return 'overlaps_requested_period'
    return 'incomplete_date_metadata_review_required'


def metadata_field_names(metadata):
    """Handle row-oriented, transposed and nested metadata responses."""
    names = set()

    def collect(item):
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            for key, entry in item.items():
                collect(key)
                collect(entry)
        elif isinstance(item, (list, tuple)):
            for entry in item:
                collect(entry)

    collect(metadata.index.tolist())
    collect(metadata.columns.tolist())
    collect(metadata.to_numpy(dtype=object).tolist())
    return names


def available_fields():
    metadata = search_content.metadata.Definition(
        view=search_content.Views.EQUITY_QUOTES
    ).get_data().data.df
    if metadata is None or metadata.empty:
        raise RuntimeError('LSEG returned no EquityQuotes metadata.')
    names = metadata_field_names(metadata)
    required = {'RIC', 'DocumentTitle', 'TickerSymbol', 'BusinessEntity',
                'ExchangeCountry', 'RCSAssetCategoryLeaf'}
    if not required.issubset(names):
        raise RuntimeError(
            'Missing search properties: ' + ', '.join(sorted(required - names))
            + f'. Metadata shape: {metadata.shape}; columns: {list(metadata.columns)}. '
            + 'No broad search fallback was used.'
        )
    return [field for field in FIELDS if field in names]


def find_candidates(ticker, fields, top, pause):
    # Do not filter IsActive/ListingStatus: inactive/delisted quotes are needed.
    categories = ' or '.join(
        f"RCSAssetCategoryLeaf eq '{literal(category)}'"
        for category in STOCK_CATEGORIES
    )
    base = ("BusinessEntity eq 'QUOTExEQUITY' and ExchangeCountry eq 'USA'"
            f' and ({categories})')
    variants = list(dict.fromkeys([ticker, ticker.replace('-', '.')]))
    ticker_filter = ' or '.join(f"TickerSymbol xeq '{literal(t)}'" for t in variants)
    # Archived RICs may retain the old symbol even if TickerSymbol changed.
    ric_filter = ' or '.join(
        f"(RIC eq '{literal(t)}.*' or RIC eq '{literal(t)}^*' or RIC xeq '{literal(t)}')"
        for t in variants
    )
    jobs = [
        ('ticker_exact', None, f'({ticker_filter})'),
        ('historical_ric_root', None, f'({ric_filter})'),
    ]
    if ticker in NAME_HINTS:
        jobs.append(('company_name_hint', NAME_HINTS[ticker], None))
    found, errors, capped = [], [], []
    for method, query, extra in jobs:
        kwargs = dict(view=ld.discovery.Views.EQUITY_QUOTES,
                      filter=base + (f' and {extra}' if extra else ''),
                      select=','.join(fields), top=top)
        if query:
            kwargs['query'] = query
        try:
            result = ld.discovery.search(**kwargs)
            if result is None or result.empty:
                continue
            if 'RIC' not in result.columns:
                raise RuntimeError(f'RIC missing; returned columns: {list(result.columns)}')
            if len(result) >= top:
                capped.append(method)
            result = result.loc[result['RIC'].notna()].copy()
            result['search_method'] = method
            found.extend(result.to_dict('records'))
        except Exception as exc:
            errors.append({'ticker': ticker, 'search_method': method,
                           'error_type': type(exc).__name__, 'error': str(exc)})
        finally:
            time.sleep(pause)
    return found, errors, capped


def relevant_stock(record, ticker, start, end):
    if value(record, 'RCSAssetCategoryLeaf') not in STOCK_CATEGORIES:
        return False
    if period_check(record, start, end) == 'outside_requested_period':
        return False
    symbol = normalized_ticker(value(record, 'TickerSymbol'))
    wanted = normalized_ticker(ticker)
    ric = normalized_ticker(value(record, 'RIC'))
    root_match = ric == wanted or ric.startswith(wanted + '.') or ric.startswith(wanted + '^')
    title = value(record, 'DocumentTitle').casefold()
    hint = NAME_HINTS.get(ticker, '')
    name_match = bool(hint) and all(word.casefold() in title for word in hint.split())
    return symbol == wanted or root_match or name_match


def primary_flag(record):
    return value(record, 'IsPrimaryIssueRIC').lower() == 'true'


def candidate_rows(ticker, records, errors, capped, start, end):
    by_ric = {}
    for record in records:
        if not relevant_stock(record, ticker, start, end):
            continue
        ric = value(record, 'RIC')
        if not ric:
            continue
        if ric not in by_ric:
            by_ric[ric] = (record, set())
        by_ric[ric][1].add(record['search_method'])
    groups = {}
    for ric, (record, methods) in by_ric.items():
        isin = value(record, 'ISIN') or value(record, 'IssueISIN')
        # Only a shared security identifier justifies grouping venue quotes.
        key = ('isin', isin) if isin else ('ric', ric)
        groups.setdefault(key, []).append((ric, record, methods))
    common = {
        'ticker': ticker, 'security_candidate_count': len(groups),
        'quote_candidate_count': len(by_ric), 'capped_queries': ';'.join(capped),
        'error': ' | '.join(f"{e['search_method']}: {e['error_type']}: {e['error']}" for e in errors),
        'approved': False, 'requested_start': start, 'requested_end': end,
    }
    if not groups:
        return [{**common, 'status': 'search_error' if errors else 'not_found',
                 'review_note': 'No matching stock found; this does not prove history is unavailable.'}]
    rows = []
    for entries in groups.values():
        entries.sort(key=lambda entry: (not primary_flag(entry[1]), entry[0]))
        ric, record, _ = entries[0]
        status = 'multiple_securities_review' if len(groups) > 1 else 'single_security_review'
        if errors or capped:
            status = 'incomplete_search_review'
        rows.append({
            **common, 'status': status,
            'company': value(record, 'DocumentTitle'), 'ric': ric,
            'alternative_rics': ';'.join(entry[0] for entry in entries[1:]),
            'isin': value(record, 'ISIN') or value(record, 'IssueISIN'),
            'quote_permid': value(record, 'PermID'),
            'exchange': value(record, 'ExchangeName'),
            'asset_category': value(record, 'RCSAssetCategoryLeaf'),
            'listing_status': value(record, 'ListingStatus'),
            'issue_date': value(record, 'IssueDate'),
            'retire_date': value(record, 'RetireDate'),
            'ticker_exact': normalized_ticker(value(record, 'TickerSymbol')) == normalized_ticker(ticker),
            'period_check': period_check(record, start, end),
            'search_methods': ';'.join(sorted(set().union(*(entry[2] for entry in entries)))),
            'review_note': 'RIC represents venue quotes grouped by ISIN; historical identity and price availability still require verification.',
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--tickers', nargs='+')
    source.add_argument('--input', type=Path, help='TXT, one ticker per line; or universe CSV')
    parser.add_argument('--start', default='2008-01-01')
    parser.add_argument('--end', default='2026-08-18')
    parser.add_argument('--output', type=Path, help='Single output CSV path')
    parser.add_argument('--top', type=int, default=200)
    parser.add_argument('--pause', type=float, default=0.3)
    args = parser.parse_args()
    if args.input and not args.input.is_absolute():
        args.input = Path(__file__).resolve().parent / args.input
    if args.top < 1 or args.pause < 0 or pd.Timestamp(args.start) > pd.Timestamp(args.end):
        parser.error('Invalid top, pause or date range')
    requests = dict(DEFAULT_REQUESTS)
    if args.input and args.input.suffix.lower() == '.csv':
        data = pd.read_csv(args.input, dtype=str, keep_default_na=False)
        if 'ticker' not in data:
            parser.error('Input CSV must contain ticker')
        # A universe export also contains fully covered stocks: omit those.
        if 'price_coverage_during_membership' in data:
            data = data.loc[pd.to_numeric(data['price_coverage_during_membership'], errors='coerce') < 1]
        tickers = data['ticker'].tolist()
        for row in data.to_dict('records'):
            requests[row['ticker']] = (row.get('first_membership_date') or args.start,
                                       row.get('last_membership_date') or args.end)
    elif args.input:
        tickers = args.input.read_text(encoding='utf-8-sig').splitlines()
    else:
        tickers = args.tickers or DEFAULT_TICKERS
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not tickers:
        parser.error('No tickers to search')
    if any(not re.fullmatch(r'[A-Z0-9.\-]+', t) for t in tickers):
        parser.error('Unexpected ticker format in input')
    output = args.output or Path(__file__).resolve().parent / ('lseg_mapping_' + time.strftime('%Y%m%d_%H%M%S') + '.csv')
    if output.exists():
        parser.error(f'Output already exists: {output}. Choose another --output filename.')
    output.parent.mkdir(parents=True, exist_ok=True)
    all_candidates = []
    ld.open_session()
    try:
        try:
            fields = available_fields()
        except Exception as exc:
            pd.DataFrame([
                {'ticker': ticker, 'status': 'metadata_error',
                 'error': f'{type(exc).__name__}: {exc}', 'approved': False}
                for ticker in tickers
            ]).reindex(columns=OUTPUT_COLUMNS).to_csv(output, index=False, encoding='utf-8-sig')
            raise
        print('Selected fields:', ', '.join(fields))
        print(f'Tickers to process: {len(tickers)}')
        print(f'Single output file: {output.resolve()}')
        for number, ticker in enumerate(tickers, 1):
            records, errors, capped = find_candidates(ticker, fields, args.top, args.pause)
            start, end = requests.get(ticker, (args.start, args.end))
            rows = candidate_rows(ticker, records, errors, capped, start, end)
            all_candidates.extend(rows)
            # Checkpoint after each ticker; partial results survive interruption.
            pd.DataFrame(all_candidates).reindex(columns=OUTPUT_COLUMNS).to_csv(
                output, index=False, encoding='utf-8-sig')
            print(f"{number}/{len(tickers)} {ticker}: "
                  f"{rows[0]['security_candidate_count']} securities, {len(errors)} errors")
    finally:
        ld.close_session()
    print(f'\nSaved to: {output.resolve()}')
    print('Review historical company, security identity and dates before setting approved=True.')
    print('No historical prices were downloaded or merged.')


if __name__ == '__main__':
    main()
