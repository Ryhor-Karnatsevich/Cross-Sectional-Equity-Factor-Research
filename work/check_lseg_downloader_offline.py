"""Offline checks only: a fake LSEG session is used; no university requests."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types

import pandas as pd


fake = types.ModuleType('lseg.data')
fake.__version__ = 'offline-test'
fake.HeaderType = types.SimpleNamespace(NAME='name')
fake.open_session = lambda: None
fake.close_session = lambda: None
calls = []


def history(universe, fields, interval, start, end, count, adjustments, header_type=None):
    calls.append(('history', universe, start, adjustments))
    index = pd.bdate_range(start, end, inclusive='both')[:2]
    values = {'OPEN_PRC': [9., 10.], 'HIGH_1': [11., 12.], 'LOW_1': [8., 9.],
              'TRDPRC_1': [10., 11.], 'ACVOL_UNS': [100., 120.]}
    columns = pd.MultiIndex.from_tuples([(universe, field) for field in fields])
    frame = pd.DataFrame({field: values[field] for field in fields}, index=index)
    frame.columns = columns
    return frame


def get_data(universe, fields, parameters=None, header_type=None):
    calls.append(('data', universe[0], str(parameters)))
    if fields[0] == 'TR.ISIN':
        return pd.DataFrame({'TR.ISIN': ['US0213461017'], 'TR.CommonName': ['Altaba'],
                             'TR.PriceClose.Currency': ['USD']})
    index = pd.bdate_range(parameters['SDate'], parameters['EDate'])[:2]
    return pd.DataFrame({
        'Instrument': [universe[0]] * 3,
        'TR.TotalReturn1D.date': [index[0], index[1], index[1]],
        'TR.TotalReturn1D': [1., 2., 2.],
    })


fake.get_history = history
fake.get_data = get_data
parent = types.ModuleType('lseg')
parent.data = fake
sys.modules['lseg'] = parent
sys.modules['lseg.data'] = fake
script = Path(__file__).with_name('lseg_download_209.py')
module = runpy.run_path(str(script), run_name='offline_check')
ns = module['main'].__globals__
requests = json.loads(ns['EMBEDDED_REQUESTS'])
assert len(requests) == len({r['ticker'] for r in requests}) == 209
assert list(ns['chunks']())[0][0] == '2008-01-01'
assert list(ns['chunks']())[-1][-1] == '2026-08-18'

with tempfile.TemporaryDirectory() as folder:
    ns['OUTPUT_DIR'] = Path(folder) / 'download'
    ns['PAUSE_SECONDS'] = 0
    ns['OUTPUT_DIR'].mkdir()
    (ns['OUTPUT_DIR'] / 'Datasets').mkdir()
    item = requests[0]
    row = ns['download_security'](item)
    assert row['status'] == 'DOWNLOADED_CANDIDATE', row
    panel = pd.read_csv(ns['OUTPUT_DIR'] / row['data_file'])
    assert len(panel) == 8
    assert panel.date.is_unique
    assert panel['total_return_1d_provider_value'].tolist() == [1., 2.] * 4
    assert panel['volume_unadjusted'].tolist() == [100., 120.] * 4
    assert row['reference_currency'] == 'USD'
    before = len(calls)
    ns['download_security'](item)
    assert len(calls) == before, 'Successful requests should be reused from raw cache'
    conflicting = get_data([item['ric']], ['TR.TotalReturn1D.date'],
                           {'SDate': '2020-01-01', 'EDate': '2020-01-10'})
    conflicting.loc[2, 'TR.TotalReturn1D'] = 99.
    try:
        ns['parse_total_return'](conflicting, '2020-01-01', '2020-01-10')
        raise AssertionError('Conflicting dates must be rejected')
    except ValueError:
        pass
    ns['OUTPUT_DIR'] = Path(folder) / 'complete_run'
    original_download = ns['download_security']
    ns['download_security'] = lambda item: {
        'ticker': item['ticker'], 'ric': item['ric'], 'status': 'OFFLINE_SIMULATION'
    }
    with contextlib.redirect_stdout(io.StringIO()):
        ns['main']()
    report = pd.read_csv(ns['OUTPUT_DIR'] / 'download_report.csv')
    assert len(report) == report.ticker.nunique() == 209
    ns['download_security'] = original_download

print('PASS: embedded 209 identities; chunk boundaries; MultiIndex pricing; actual-date returns;')
print('duplicate/conflict handling; unchanged provider units; raw cache round-trip/resume;')
print('one 209-row report. Fake session only; no live LSEG requests.')
