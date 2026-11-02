# LSEG recovery: actual merged data

Data revision: `yahoo_lseg_prepared_20261102`. This report describes files already saved in `Data/Data_System`, rather than projected coverage from recovery candidates.

| Metric | Actual result |
| --- | ---: |
| Trading dates | 4,686 |
| Historical ticker columns | 900 |
| LSEG histories incorporated | 250 |
| Original price and volume columns left unchanged | 650 |
| Required ticker-date observations during membership | 2,350,698 |
| Available prices passing price quality during membership | 2,316,601 |
| Remaining missing membership observations | 34,097 |
| Membership price coverage before recovery | 81.7481% |
| Membership price coverage after recovery | **98.5495%** |
| Membership price coverage from 2015 onwards | **99.0474%** |
| Final Data System audit | **53 PASS / 5 WARNING / 0 FAIL** |

Coverage uses ticker-date observations inside actual index membership. It is not an estimate of the percentage of survivorship bias eliminated.

## Preparation and integration

- Original LSEG CSV and JSON downloads are retained under `LSEG_Recovery`; the pre-merge project datasets and reports are backed up in `LSEG_Recovery/Preparation/Backup_before_merge_20261102`.
- LSEG `TR.TotalReturn1D` is interpreted as a percentage and used to reconstruct return-compatible price series. Corporate-action-adjusted close alone is not treated as dividend-adjusted Yahoo close.
- Each connected segment is anchored to an observed raw close. Missing raw prices are not fabricated. Unsupported return links remain excluded; a segment is not joined through an unknown total return.
- Compatible volume preserves `prepared price * compatible volume = raw close * raw volume`.
- Existing Yahoo observations are retained where overlap establishes a compatible return history. Separate later Yahoo security episodes are preserved when their long gaps prevent the configured research horizons from joining the episodes.
- Returns, 21-day forward returns, liquidity, price quality, volume quality, membership, availability and long-format prices were rebuilt together and audited after publication.
- `Processed/price_source.parquet` records every price cell: `0` = missing, `1` = Yahoo, `2` = prepared LSEG. `Raw/lseg_preparation_sources.csv` records source identifiers, files and hashes.
- GGP's real 2008-11-24 move was added to the confirmed-event list after checking the raw observations and an [independent contemporary report](https://www.dailyherald.com/20081124/business/general-growth-shares-jump-after-pershing-square-buys-stake/). This prevents an erroneous permanent quarantine.

All 14 published data and provenance files were checked against their prepared SHA-256 hashes. The price-source matrix was checked against actual price presence. No download pipeline was added.

## Deliberately unresolved

- **IR, FOX and FOXA:** three recovered old-company histories are prepared separately but not incorporated. Correct integration requires separate old/new security columns and corresponding membership intervals. Their existing main-dataset columns remain unchanged pending approval of that change.
- **HES:** 1,259 membership dates in 2013-2017 have prices but no usable downloaded total-return observations. Their original source observations are preserved, while the prepared research prices remain missing rather than silently substituting price-only returns.
- Other unresolved historical securities remain missing. Small boundary gaps remain missing as well.

The earlier theoretical **98.8455%** assumed all 253 candidates and counted available raw prices. With the three identity histories separated, prepared coverage would be **98.7919%**; it remains below the raw-price projection because of the HES return gap. The currently published coverage is **98.5495%**.

## Remaining audit warnings

1. File modification times differ because unchanged original history and macro files retain their earlier timestamps.
2. Some historical securities still have incomplete or unavailable prices.
3. There are 23 missing-price runs longer than five trading dates, covering 34,030 observations across 20 tickers; these are reported and not filled.
4. Fourteen zero-volume observations remain in stored volume and are excluded from liquidity input by volume quality.
5. Thirty-two positive-to-positive volume jumps of at least 100 times remain as diagnostic warnings; positive volume alone does not establish an error.

Full check results: [data_audit_report.md](data_audit_report.md).

## Scope of this revision

The existing Data System datasets are updated. Factor, selection and portfolio results have **not** been recalculated and still describe the previous data revision. Rebuilding data from Yahoo alone or deleting the Data System files would discard this one-off merge; the preserved recovery sources and preparation utility can reproduce it. The one-off utility is `LSEG_Recovery/Preparation/prepare_merge_once.py`; it prepares staging files and is not a new project pipeline.
