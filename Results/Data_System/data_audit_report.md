# Data System Audit Report

- Checked at: `2026-11-02T23:44:28+01:00`
- Overall status: **WARNING**
- Bundle fingerprint: `720466b18a18e6077bb93b4194478c307c5d87c7640c3768543f438e3d36bf8c`
- Checks: PASS 53 / WARNING 5 / FAIL 0
- Audit mode: read-only; no data were downloaded, deleted or corrected.

## Checks

| # | Section | Status | Check | Result |
| ---: | --- | --- | --- | --- |
| 1 | Files | **PASS** | prices | File opens successfully |
| 2 | Files | **PASS** | returns | File opens successfully |
| 3 | Files | **PASS** | volume | File opens successfully |
| 4 | Files | **PASS** | volume_quality | File opens successfully |
| 5 | Files | **PASS** | liquidity | File opens successfully |
| 6 | Files | **PASS** | prices_long | File opens successfully |
| 7 | Files | **PASS** | availability | File opens successfully |
| 8 | Files | **PASS** | forward_returns | File opens successfully |
| 9 | Files | **PASS** | membership | File opens successfully |
| 10 | Files | **PASS** | quality | File opens successfully |
| 11 | Files | **PASS** | universe | File opens successfully |
| 12 | Files | **PASS** | historical_components | File opens successfully |
| 13 | Files | **PASS** | risk_free_rate | File opens successfully |
| 14 | Files | **WARNING** | Equity file generation times | Modification-time spread: 1251.56 hours |
| 15 | Matrices | **PASS** | Price date index | Rows: 4,686; dates: 2008-01-02 00:00:00 -> 2026-08-18 00:00:00 |
| 16 | Matrices | **PASS** | Unique price tickers | Tickers: 900 |
| 17 | Matrices | **PASS** | Valid observed prices | Non-positive: 0; infinite: 0 |
| 18 | Matrices | **PASS** | returns alignment | Shape: (4686, 900); expected: (4686, 900) |
| 19 | Matrices | **PASS** | volume alignment | Shape: (4686, 900); expected: (4686, 900) |
| 20 | Matrices | **PASS** | volume_quality alignment | Shape: (4686, 900); expected: (4686, 900) |
| 21 | Matrices | **PASS** | liquidity alignment | Shape: (4686, 900); expected: (4686, 900) |
| 22 | Matrices | **PASS** | availability alignment | Shape: (4686, 900); expected: (4686, 900) |
| 23 | Matrices | **PASS** | forward_returns alignment | Shape: (4686, 900); expected: (4686, 900) |
| 24 | Matrices | **PASS** | membership alignment | Shape: (4686, 900); expected: (4686, 900) |
| 25 | Matrices | **PASS** | quality alignment | Shape: (4686, 900); expected: (4686, 900) |
| 26 | Matrices | **PASS** | availability boolean dtype | All columns are boolean |
| 27 | Matrices | **PASS** | membership boolean dtype | All columns are boolean |
| 28 | Matrices | **PASS** | quality boolean dtype | All columns are boolean |
| 29 | Matrices | **PASS** | volume_quality boolean dtype | All columns are boolean |
| 30 | Quality | **PASS** | Quality requires a positive observed price | Invalid True cells: 0 |
| 31 | Calculations | **PASS** | Daily returns reproduce from prices and quality | Mismatched cells: 0 |
| 32 | Quality | **PASS** | Unclipped large returns | Absolute returns >=50%: 203; unconfirmed returns >=100%: 0 |
| 33 | Calculations | **PASS** | 21-day forward returns reproduce from prices and quality | Mismatched cells: 0 |
| 34 | Calculations | **PASS** | Availability formula | Mismatched cells: 0 |
| 35 | Calculations | **PASS** | Liquidity formula | Mismatched cells: 0 |
| 36 | Calculations | **PASS** | Long prices rows and uniqueness | Rows: 3,390,075; expected: 3,390,075; duplicate date-ticker pairs: 0 |
| 37 | Calculations | **PASS** | Long prices reproduce wide prices | Same keys: True; mismatched prices: 0 |
| 38 | Universe | **PASS** | Historical component snapshots | Snapshots: 2,720; component range: 496 -> 507 |
| 39 | Universe | **PASS** | Membership reproduces from historical snapshots | Mismatched cells: 0 |
| 40 | Universe | **PASS** | Price data does not exceed membership source | Last price: 2026-08-18 00:00:00; last snapshot: 2026-08-18 00:00:00 |
| 41 | Universe | **PASS** | Universe report schema | Missing columns: none |
| 42 | Universe | **PASS** | Universe report matches price columns | Only in universe: 0; only in prices: 0 |
| 43 | Universe | **PASS** | Universe contains the historical ticker union | Source union: 900; report: 900; difference: 0 |
| 44 | Universe | **PASS** | Valid membership coverage values | Invalid rows: 0 |
| 45 | Universe | **WARNING** | Historical data availability | No prices during membership: 17; coverage below 80%: 21; missing downloads: 12; rejected reused symbols: 1 |
| 46 | Universe | **PASS** | Universe membership counts | Mismatched tickers: 0 |
| 47 | Prices | **WARNING** | Missing-price runs longer than 5 trading dates during membership | Found 23 runs (34,030 observations) across 20 tickers. Longest runs: MYL: 3243 trading dates (2008-01-02 -> 2020-11-16); AGN: 3111 trading dates (2008-01-02 -> 2020-05-11); DISCA: 3051 trading dates (2010-03-01 -> 2022-04-08); CBS: 3003 trading dates (2008-01-02 -> 2019-12-04); BHGE: 2970 trading dates (2008-01-02 -> 2019-10-17); FOXA: 2816 trading dates (2008-01-02 -> 2019-03-11); WYND: 2621 trading dates (2008-01-02 -> 2018-05-30); CCE: 2117 trading dates (2008-01-02 -> 2016-05-27); IR: 1631 trading dates (2010-11-17 -> 2017-05-11); HES: 1259 trading dates (2013-01-02 -> 2017-12-29). The audit reports these gaps but does not fill or remove them. |
| 48 | Volume | **PASS** | Valid volume values | Negative: 0; infinite: 0 |
| 49 | Volume | **PASS** | Volume quality formula | Mismatched cells: 0 |
| 50 | Volume | **WARNING** | Missing and zero volume during membership | Relevant observations: 2,316,601; missing: 0 (0.0000%); zero: 14 (0.0006%) |
| 51 | Volume | **PASS** | Raw invalid volume excluded by volume_quality | Invalid raw observations: 14; excluded: 14; still accepted: 0 |
| 52 | Volume | **WARNING** | Positive volume jumps remaining after volume_quality >= 100x | Remaining positive-to-positive events: 32 across 27 tickers; most affected: BIIB: 4, BF-B: 2, HUBB: 2, AMTM: 1, AMGN: 1, BEN: 1, BRK-B: 1, CINF: 1, COST: 1, EMN: 1. Not removed automatically because both observations are valid positive volumes. |
| 53 | Volume | **PASS** | Runs of at least 5 missing/zero volume observations | Found 0 runs (0 observations) across 0 tickers: None. |
| 54 | Volume | **PASS** | Long missing/zero runs excluded by volume_quality | Observations inside long runs: 0; excluded: 0; still accepted: 0 |
| 55 | Volume | **PASS** | Invalid volume excluded from liquidity inputs | Excluded from volume/liquidity analysis while retained for price analysis: 14 observations |
| 56 | Risk-free rate | **PASS** | DGS3MO schema | Columns: ['annual_rate_pct'] |
| 57 | Risk-free rate | **PASS** | Valid DGS3MO observations | Observed: 4,660; missing: 200; negative: 0; infinite: 0 |
| 58 | Risk-free rate | **PASS** | DGS3MO covers the equity period | Rates: 2008-01-02 00:00:00 -> 2026-08-18 00:00:00; equities: 2008-01-02 00:00:00 -> 2026-08-18 00:00:00 |

## File inventory

| Dataset | File | State | Size | Modified |
| --- | --- | --- | --- | --- |
| prices | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\prices.parquet` | FOUND | 24.02 MB | 2026-11-02T18:51:23+01:00 |
| returns | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\returns.parquet` | FOUND | 31.08 MB | 2026-11-02T18:51:23+01:00 |
| volume | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\volume.parquet` | FOUND | 29.79 MB | 2026-11-02T18:51:23+01:00 |
| volume_quality | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\volume_quality.parquet` | FOUND | 0.43 MB | 2026-11-02T18:51:23+01:00 |
| liquidity | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\liquidity.parquet` | FOUND | 31.23 MB | 2026-11-02T18:51:23+01:00 |
| prices_long | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\prices_long.parquet` | FOUND | 22.19 MB | 2026-11-02T18:51:23+01:00 |
| availability | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\availability.parquet` | FOUND | 0.43 MB | 2026-11-02T18:51:23+01:00 |
| forward_returns | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\forward_returns.parquet` | FOUND | 31.17 MB | 2026-11-02T18:51:23+01:00 |
| membership | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\membership.parquet` | FOUND | 0.43 MB | 2026-11-02T18:51:23+01:00 |
| quality | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Processed\data_quality.parquet` | FOUND | 0.43 MB | 2026-11-02T18:51:23+01:00 |
| universe | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\universe.csv` | FOUND | 0.08 MB | 2026-11-02T18:51:23+01:00 |
| historical_components | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\sp500_historical_components.csv` | FOUND | 5.27 MB | 2026-09-11T16:18:01+02:00 |
| risk_free_rate | `C:\Users\God\PycharmProjects\Cross-Sectional Alpha Modeling and Portfolio Construction\Data\Data_System\Raw\dgs3mo.parquet` | FOUND | 0.05 MB | 2026-09-11T16:24:01+02:00 |

## Interpretation

- **FAIL** means that a file or a mathematical relationship is incorrect.
- **WARNING** means that the dataset remains usable only with a documented limitation.
- **PASS** means that the specific internal check succeeded.

## Limits of this audit

- Internal consistency does not prove that Yahoo or the historical membership source is correct.
- Missing delisted securities and survivorship/data-availability bias cannot be repaired by this audit.
- Modification times help detect mixed builds but do not make multi-file saving atomic.
- Large price and volume moves are diagnostics; economic reality may require an external source.
