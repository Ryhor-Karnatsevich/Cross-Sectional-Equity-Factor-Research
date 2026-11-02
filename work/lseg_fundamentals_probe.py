"""Run normally on the university PC with LSEG Workspace signed in.

Requires: pip install lseg-data pandas
Checks access/coverage only; does not calculate Fama-French factors.
"""
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
import time

import pandas as pd
import lseg.data as ld


COMPANIES = [
    ('AAPL', 'Apple', 'AAPL.O'),
    ('MSFT', 'Microsoft', 'MSFT.O'),
    ('JPM', 'JPMorgan Chase', 'JPM.N'),
    ('CELG', 'Celgene (delisted)', 'CELG.O^K19'),
    ('TWTR', 'Twitter (delisted)', 'TWTR.N^J22'),
    ('MER', 'Merrill Lynch (delisted)', 'MER.N^A09'),
]
START_DATE = '2006-01-01'  # Prior annual statements needed for growth/lagged characteristics.
END_DATE = '2026-08-18'    # Same historical endpoint as the existing equity dataset.
PAUSE_SECONDS = 0.3
METRICS = [
    ('market_cap', 'TR.CompanyMarketCapitalization', 'monthly', 'numeric'),
    ('common_equity', 'TR.F.ComEqTot', 'annual', 'numeric'),
    ('total_assets', 'TR.F.TotAssets', 'annual', 'numeric'),
    ('revenue', 'TR.F.TotRevenue', 'annual', 'numeric'),
    ('cost_of_goods_sold', 'TR.F.COGSTot', 'annual', 'numeric'),
    ('selling_general_administrative', 'TR.F.SGATot', 'annual', 'numeric'),
    ('interest_expense', 'TR.F.IntrExpn', 'annual', 'numeric'),
    ('original_announcement_date', 'TR.F.OriginalAnnouncementDate', 'annual', 'datetime'),
]

NOTES = '''# LSEG fundamentals access/coverage probe

Six candidate securities, eight fields. This tests actual university entitlements,
field support and returned historical coverage, including three delisted securities.

FILES:
coverage_report.csv: one summary row per company/field, including errors.
fundamentals_observations.csv: long-form returned values and their own dates/periods.
Raw/: original tables for each separate request; no cross-field row alignment assumed.
run_metadata.json: exact fields, dates, parameters, library version and candidates.

All monetary fields are requested in USD with Scale=0. Check units/definitions in
Workspace Data Item Browser; a request parameter is not proof of content semantics.
Annual statements use Period=FY0, Frq=FY; market cap uses Frq=M. Market cap history
is monthly, not today's market cap carried into the past.

provider_date is the date returned by that field's .date property. Its meaning is
NOT assumed to be the date the value became publicly available. fiscal_period is
the field's .fperiod label when supported. Each metric is requested separately;
missing/unequal financial dates must never be joined by row number.

OriginalAnnouncementDate is requested as a separate metric with fiscal-period
labels where available. Its presence does NOT prove accounting values are original
historical vintages: currently restated values could be tagged to an old announcement.
Every output has point_in_time_verified=False. No historical availability date is
fabricated; none of these values is approved for backtesting automatically.

HISTORY_FOUND means values with dates were returned, not complete coverage or a
validated Fama-French input. Market cap must be checked at company/share-class level.
TR.F.ComEqTot is a candidate common-equity field, not a verified reconstruction of
Fama-French book equity. Expense signs, preferred equity, deferred tax and minority
interest treatment require methodological reconciliation before exact replication.
Bank financial-statement definitions may differ from industrial companies.

No filling, zero substitution, factor calculation, source merging or project pipeline
changes. Missing delisted results do not prove LSEG has no fundamentals; reference
identifier linking and subscription coverage may be responsible.

Sources:
https://developers.lseg.com/en/article-catalog/article/probabilistic-relative-valuation-for-the-financial-sector-using-deep-learning
https://community.developers.lseg.com/discussion/81795/date-in-dataframe-of-fundamental-data
https://community.developers.lseg.com/discussion/132516/fewer-observations-when-downloading-data-again
'''


def headers():
    params = inspect.signature(ld.get_data).parameters
    if 'header_type' in params:
        return {'header_type': ld.HeaderType.NAME}
    if 'use_field_names_in_headers' in params:
        return {'use_field_names_in_headers': True}
    return {}


def find_column(frame, field):
    matches = []
    for column in frame.columns:
        parts = column if isinstance(column, tuple) else (column,)
        if field.casefold() in {str(part).casefold() for part in parts}:
            matches.append(column)
    if len(matches) > 1:
        raise ValueError(f'Ambiguous columns for {field}: {matches}')
    return matches[0] if matches else None


def make_parameters(frequency, data_type):
    params = {'SDate': START_DATE, 'EDate': END_DATE,
              'Frq': 'M' if frequency == 'monthly' else 'FY'}
    if frequency == 'annual':
        params['Period'] = 'FY0'
    if data_type == 'numeric':
        params.update({'Curn': 'USD', 'Scale': 0})
    return params


def get_frame(ric, fields, parameters):
    try:
        frame = ld.get_data(universe=[ric], fields=fields, parameters=parameters, **headers())
        if frame is None:
            return pd.DataFrame()
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f'Expected DataFrame, received {type(frame).__name__}')
        return frame
    finally:
        time.sleep(PAUSE_SECONDS)


def probe_metric(ticker, company, ric, metric, field, frequency, data_type, output):
    parameters = make_parameters(frequency, data_type)
    fields = [field, field + '.date']
    if frequency == 'annual':
        fields.append(field + '.fperiod')
    report = {
        'ticker': ticker, 'company': company, 'ric': ric, 'metric': metric,
        'field': field, 'frequency': frequency,
        'currency_requested': 'USD' if data_type == 'numeric' else '',
        'scale_requested': 0 if data_type == 'numeric' else '',
        'requested_start': START_DATE, 'requested_end': END_DATE,
        'point_in_time_verified': False, 'status': 'REQUEST_ERROR',
        'returned_rows': 0, 'valid_values': 0, 'dated_values': 0,
        'earliest_provider_date': '', 'latest_provider_date': '',
        'fiscal_periods': '', 'warning': '', 'error': '',
    }
    raw_path = output / 'Raw' / f'{ticker}_{metric}.csv'
    try:
        try:
            frame = get_frame(ric, fields, parameters)
            # A service can report an unsupported optional property via missing columns.
            if frequency == 'annual' and find_column(frame, field) is None:
                raise ValueError('Extended request returned no value column')
        except Exception as extended_error:
            if frequency != 'annual':
                raise
            report['warning'] = f'Extended field/period request failed; retried value+date: {extended_error}'
            frame = get_frame(ric, [field, field + '.date'], parameters)
        frame.to_csv(raw_path, index=False, encoding='utf-8-sig')
        report['returned_rows'] = len(frame)
        if frame.empty:
            report['status'] = 'EMPTY'
            return report, []
        value_col = find_column(frame, field)
        if value_col is None:
            raise ValueError(f'Value column absent; original headers: {list(frame.columns)}')
        date_col = find_column(frame, field + '.date')
        period_col = find_column(frame, field + '.fperiod')
        values = frame[value_col]
        valid = (pd.to_numeric(values, errors='coerce').notna() if data_type == 'numeric'
                 else pd.to_datetime(values, errors='coerce', utc=True).notna())
        provider_dates = (pd.to_datetime(frame[date_col], errors='coerce', utc=True)
                          if date_col is not None
                          else pd.Series(pd.NaT, index=frame.index, dtype='datetime64[ns, UTC]'))
        dated = valid & provider_dates.notna()
        observed_dates = provider_dates[dated]
        report.update({
            'valid_values': int(valid.sum()), 'dated_values': int(dated.sum()),
            'earliest_provider_date': observed_dates.min().isoformat() if len(observed_dates) else '',
            'latest_provider_date': observed_dates.max().isoformat() if len(observed_dates) else '',
            'fiscal_periods': ';'.join(sorted(frame[period_col].dropna().astype(str).unique()))
                              if period_col is not None else '',
            'status': 'HISTORY_FOUND' if dated.any() else 'VALUES_WITHOUT_DATES' if valid.any() else 'EMPTY',
        })
        observations = []
        for position in range(len(frame)):
            row = frame.iloc[position]
            if not valid.iloc[position]:
                continue
            value = row[value_col]
            if isinstance(value, (pd.Timestamp, datetime)):
                value = value.isoformat()
            observations.append({
                'ticker': ticker, 'company': company, 'ric': ric,
                'metric': metric, 'field': field, 'frequency': frequency,
                'provider_date': row[date_col] if date_col is not None else '',
                'fiscal_period': row[period_col] if period_col is not None else '',
                'provider_value': value, 'currency_requested': report['currency_requested'],
                'scale_requested': report['scale_requested'], 'point_in_time_verified': False,
            })
        return report, observations
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        return report, []


def main():
    output = Path(__file__).resolve().parent / ('lseg_fundamentals_probe_' +
              datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True)
    (output / 'Raw').mkdir()
    (output / 'README.md').write_text(NOTES, encoding='utf-8')
    (output / 'run_metadata.json').write_text(json.dumps({
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'lseg_version': getattr(ld, '__version__', 'unknown'),
        'companies': COMPANIES, 'metrics': METRICS,
        'start': START_DATE, 'end': END_DATE,
        'parameters_by_metric': {m: make_parameters(f, t) for m, _, f, t in METRICS},
        'point_in_time_verified': False,
    }, indent=2), encoding='utf-8')
    print(f'Pilot: {len(COMPANIES)} companies, {len(METRICS)} fields. Output: {output}', flush=True)
    reports, observations = [], []
    ld.open_session()
    try:
        # A real uncached request prevents a disconnected session from starting the whole loop.
        live = ld.get_data(universe=['AAPL.O'], fields=['TR.CommonName'], **headers())
        if live is None or live.empty or live.drop(columns=['Instrument'], errors='ignore').dropna(how='all').empty:
            raise RuntimeError('Live session check failed. Open and sign in to LSEG Workspace, then retry.')
        for ticker, company, ric in COMPANIES:
            for metric, field, frequency, data_type in METRICS:
                print(f'{ticker}: {metric}', flush=True)
                report, rows = probe_metric(ticker, company, ric, metric, field,
                                            frequency, data_type, output)
                reports.append(report)
                observations.extend(rows)
                pd.DataFrame(reports).to_csv(output / 'coverage_report.csv', index=False, encoding='utf-8-sig')
                pd.DataFrame(observations, columns=[
                    'ticker', 'company', 'ric', 'metric', 'field', 'frequency',
                    'provider_date', 'fiscal_period', 'provider_value',
                    'currency_requested', 'scale_requested', 'point_in_time_verified',
                ]).to_csv(output / 'fundamentals_observations.csv', index=False, encoding='utf-8-sig')
                print(f"  {report['status']}: {report['valid_values']} values; "
                      f"{report['earliest_provider_date']} -> {report['latest_provider_date']}", flush=True)
    except Exception as error:
        # Save diagnostics even when the session never opened successfully.
        if not reports:
            pd.DataFrame([{'status': 'SESSION_ERROR', 'error': f'{type(error).__name__}: {error}'}]).to_csv(
                output / 'coverage_report.csv', index=False, encoding='utf-8-sig')
        raise
    finally:
        ld.close_session()
    print(f'Finished. Send coverage_report.csv from {output}')


if __name__ == '__main__':
    main()
