"""Offline pilot checks. Does not contact LSEG."""
import contextlib
import io
import runpy
import sys
import tempfile
import types
from pathlib import Path
import pandas as pd

fake = types.ModuleType('lseg.data')
fake.HeaderType = types.SimpleNamespace(NAME='name')
fake.open_session = lambda: None
fake.close_session = lambda: None
requests = []


def get_data(universe, fields, parameters=None, header_type=None):
    requests.append((universe, fields, parameters))
    if fields == ['TR.CommonName']:
        return pd.DataFrame({'Instrument': universe, 'TR.CommonName': ['Apple']})
    field = fields[0]
    if field == 'TR.F.COGSTot' and len(fields) == 3:
        raise ValueError('Simulated unsupported optional .fperiod')
    if field == 'TR.F.SGATot':
        return pd.DataFrame()
    if field == 'TR.F.IntrExpn':
        return pd.DataFrame({field: [1., 2.]})
    value = ['2010-03-01', '2011-03-01'] if field.endswith('AnnouncementDate') else [10., 20.]
    frame = pd.DataFrame({field: value, field + '.date': ['2009-12-31', '2010-12-31']})
    if len(fields) == 3:
        frame[field + '.fperiod'] = ['FY2009', 'FY2010']
    return frame


fake.get_data = get_data
parent = types.ModuleType('lseg')
parent.data = fake
sys.modules['lseg'] = parent
sys.modules['lseg.data'] = fake
script = Path(__file__).with_name('lseg_fundamentals_probe.py')
module = runpy.run_path(str(script), run_name='offline_probe_check')
ns = module['main'].__globals__
ns['PAUSE_SECONDS'] = 0
with tempfile.TemporaryDirectory() as folder:
    ns['__file__'] = str(Path(folder) / script.name)
    with contextlib.redirect_stdout(io.StringIO()):
        ns['main']()
    out = next(Path(folder).glob('lseg_fundamentals_probe_*'))
    report = pd.read_csv(out / 'coverage_report.csv')
    observations = pd.read_csv(out / 'fundamentals_observations.csv')
    assert len(report) == 48
    assert report.ticker.nunique() == 6
    assert report.loc[report.metric.eq('selling_general_administrative'), 'status'].eq('EMPTY').all()
    assert report.loc[report.metric.eq('interest_expense'), 'status'].eq('VALUES_WITHOUT_DATES').all()
    assert report.loc[report.metric.eq('cost_of_goods_sold'), 'warning'].notna().all()
    assert not observations.point_in_time_verified.any()
    assert observations.loc[observations.metric.eq('original_announcement_date'), 'provider_value'].str.contains('2010-03-01|2011-03-01').all()
    before = len(requests)
    fake.get_data = lambda **kwargs: pd.DataFrame()
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            ns['main']()
            raise AssertionError('Session failure must stop execution')
        except RuntimeError:
            pass
    assert len(requests) == before
print('PASS: 48 pilot summaries; per-field dates; missing values remain missing;')
print('optional-period fallback; announcement dates preserved; no PIT claim; fail-fast session.')
