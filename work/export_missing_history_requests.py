"""Export missing membership history without changing any research datasets."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'Data' / 'Data_System'
OUT = ROOT / 'Results' / 'Data_System'


def main():
    prices = pd.read_parquet(BASE / 'Raw' / 'prices.parquet')
    membership = pd.read_parquet(BASE / 'Processed' / 'membership.parquet')
    quality = pd.read_parquet(BASE / 'Processed' / 'data_quality.parquet')
    universe = pd.read_csv(BASE / 'Raw' / 'universe.csv').set_index('ticker')
    assert prices.index.equals(membership.index)
    assert prices.columns.equals(membership.columns)
    missing = membership & prices.isna()
    rows, gaps = [], []
    for ticker in prices.columns[missing.any()]:
        mask = missing[ticker].to_numpy(dtype=bool)
        starts = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
        ends = np.flatnonzero(mask & ~np.r_[mask[1:], False])
        member_dates = prices.index[membership[ticker]]
        observed = prices.index[membership[ticker] & prices[ticker].notna()]
        first_gap = prices.index[starts[0]]
        # Calendar buffer exceeds the largest 504-trading-day factor lookback.
        request_start = max(prices.index.min(), first_gap - pd.DateOffset(years=3))
        method = str(universe.loc[ticker, 'download_method'])
        category = 'no_prices_during_membership' if len(observed) == 0 else 'partial_history'
        rows.append((ticker, category, method, str(universe.loc[ticker, 'yahoo_ticker']),
                     member_dates.min().date(), member_dates.max().date(), len(member_dates),
                     len(observed), int(mask.sum()), len(starts),
                     request_start.date(), member_dates.max().date()))
        for start, end in zip(starts, ends):
            gaps.append((ticker, prices.index[start].date(), prices.index[end].date(),
                         int(end - start + 1)))

    summary_path = OUT / 'missing_history_download_requests.md'
    gaps_path = OUT / 'missing_history_exact_gaps.md'
    ticker_path = OUT / 'missing_history_tickers.txt'
    text = [
        '# University data download requests', '',
        f'Computed from local matrices: {prices.index.min().date()} to {prices.index.max().date()}.',
        f'{len(prices.columns)} historical symbols; {len(rows)} symbols with missing membership prices; '
        f'{sum(r[1] == "no_prices_during_membership" for r in rows)} with no membership prices; '
        f'{int(missing.sum().sum()):,} missing ticker-date observations.', '',
        'These are observed coverage gaps, not proof that Yahoo has no history and not a list of securities proven to cause survivorship bias.',
        'Dates are inclusive. Exact gap dates refer to the stored trading-date index. Missing prices outside index membership are not counted here.',
        'Request start adds up to three calendar years before the first gap for factor warm-up, clipped to the existing dataset start. '
        'Request end is the last membership date. This deliberately requests continuous history rather than isolated missing days.',
        'For the simplest bulk download, request every listed security for 2008-01-01 through 2026-08-18.', '',
        'Match historical company/security identity using provider identifiers (e.g. PERMNO, ISIN, CUSIP), exchange and dated ticker history. '
        'The current holder of an obsolete ticker can be a different company. Yahoo alias is a search hint only. '
        'Do not splice an acquirer into the acquired security.',
        'Obtain total-return-adjusted prices or raw prices plus dividends/split adjustments; obtain raw volume with its adjustment convention. '
        'For delisted securities also request delisting date, delisting return or final cash consideration when available. '
        'Membership-only gaps do not enumerate missing terminal payoffs or all pre-membership warm-up gaps.',
        f'Observed prices rejected by price quality during membership: {int((membership & prices.notna() & ~quality).sum().sum()):,}.', '',
        '| Ticker | Coverage category | Download status | Yahoo alias/search hint | First membership | Last membership | Membership dates | Prices present | Missing dates | Gap runs | Request from | Request through |',
        '|---|---|---|---|---|---|---:|---:|---:|---:|---|---|',
    ]
    text.extend('| ' + ' | '.join(map(str, row)) + ' |' for row in rows)
    summary_path.write_text('\n'.join(text) + '\n', encoding='utf-8')
    detail = ['# Exact missing-price intervals during membership', '',
              'Inclusive observed trading-date bounds; one row per uninterrupted missing-membership run.', '',
              '| Ticker | Missing from | Missing through | Missing trading dates |',
              '|---|---|---|---:|']
    detail.extend('| ' + ' | '.join(map(str, row)) + ' |' for row in gaps)
    gaps_path.write_text('\n'.join(detail) + '\n', encoding='utf-8')
    ticker_path.write_text('\n'.join(row[0] for row in rows) + '\n', encoding='utf-8')
    assert sum(g[3] for g in gaps) == int(missing.sum().sum())
    assert len(rows) == int(missing.any().sum())
    print(f'Saved {len(rows)} tickers, {len(gaps)} exact gaps, {sum(g[3] for g in gaps):,} missing observations.')
    print(summary_path)
    print(gaps_path)
    print(ticker_path)


if __name__ == '__main__':
    main()
