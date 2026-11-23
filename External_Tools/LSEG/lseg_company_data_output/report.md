# LSEG company data extraction

- Version: `2026-11-16-direct-get-data-full-v2`
- Companies selected: 865
- Completed request jobs: 998/998
- Finished plan: True
- New SDK calls invoked: 998
- Extracted observations: 313422
- Elapsed: 00:24:20

## Request status

| Status | Requests |
|---|---:|
| EXTRACTED | 953 |
| RAW_SAVED | 44 |
| REQUEST_ERROR | 1 |

## Files

- observations.csv: source accounting amounts, dates and monthly market cap.
- coverage.csv: counts and date ranges per company and metric.
- identities.csv: returned provider identities; compare with selected_companies.csv.
- request_report.csv: exact fields, parameters, cache source and errors.
- raw_responses.sqlite: original response tables and retrieval timestamps.
- errors.log: full exceptions, if any.

## Interpretation

These are extraction candidates, not finished Fama-French inputs. Coverage counts
are not membership-day coverage percentages. Check company identities, actual fiscal
period dates, publication dates, currency/scaling, equity/expense definitions and
duplicate records before modelling. Missing expenses are not assumed zero.
Monthly market-cap dates are preserved as returned; month-end coverage is not assumed.
Orig is a requested reporting state, not a certification of point-in-time availability.
Company capitalization can include multiple share classes; avoid double counting.
This file does not download market-factor returns or an FF-compatible risk-free series.
No price dataset, existing SEC file, factor output or main pipeline was changed.
