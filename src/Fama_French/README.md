# Fama-French Research

A separate research path for size, value, operating profitability and investment characteristics. The existing price-volume research pipelines remain unchanged.

Company inputs have been consolidated and screened. The accepted dataset is in `Data/Fama and french/Consolidated/`; the next task is to implement the declared portfolio and model rules.

- Reuse existing stock returns and point-in-time membership.
- Start from the complete historical security union, including former index members.
- Map securities to company identifiers; different tickers can share one issuer's financial statements.
- Collect annual assets, book-equity components, revenue, cost of goods sold, SG&A and interest expense.
- Keep fiscal-period dates, publication dates, reporting currency, units and source identifiers.
- Obtain historical market capitalization, or unadjusted prices and historical shares outstanding.
- Include at least two preceding fiscal years for the first annual portfolio formation, where available.
- Apply membership and data-availability rules on each formation/evaluation date.

An S&P 500 implementation tests Fama-French-style characteristics within that universe. It does not replicate the original broad-US-market factors exactly.

## Model construction rules

The complete decisions are in [METHODOLOGY.md](METHODOLOGY.md). Their machine-readable settings are in [model_config.py](model_config.py). These settings are separate from the extraction configuration and are not connected to an executable model pipeline yet.

- Compare FF3, Carhart4 and FF5 over July 2009–June 2026, using common valid months and the same test returns.
- Use accepted positive common equity as book value; do not subtract preferred equity twice or infer missing adjustments.
- Use annual June sorts for value, profitability and investment, and monthly sorts for momentum.
- Split eligible historical S&P500 issuers into Small/Big and 30%/40%/30% characteristic groups.
- Use capitalization weights within groups and the declared equal-weight combinations of group returns.
- Require all expense fields for profitability; never replace a missing expense with zero.
- Let each factor use its own eligible input sample. The market portfolio does not require accounting data.
- Apply publication dates, issuer deduplication, prior-close membership and explicit missing-held-return rules.
- Use the original-paper book-equity-only profitability denominator consistently. The current French library's minority-interest denominator is a different convention.
- Obtain the official monthly RF input when implementing the builder; do not treat the existing annualized DGS3MO yield as that return.

Only rules have been defined. No factors, portfolios, regressions or new performance results have been calculated for this research path.

## SEC extraction

Run `sec_edgar.py` directly. It reads the existing historical universe and saves files under `Data/Fama and french/`.

- Downloads complete SEC Company Facts and submissions JSON per candidate issuer.
- Preserves annual source values, publication dates, currencies and filing vintages.
- Keeps ambiguous company matches labelled as candidates; missing expenses remain missing.
- Reuses completed raw downloads on another run.
- Uses up to four workers with one shared limit below three requests per second.
- Reads the SEC contact address from the ignored output directory or `SEC_CONTACT_EMAIL`.
- Writes `report.md`, mapping, download and coverage reports, plus two Parquet tables.

The downloader is independent of all existing project pipelines. Downloaded candidates require identity and field-coverage review before factor construction.

## Offline refinement

Run `refine_sec.py` to reprocess cached Company Facts without network requests.

- Extracts additional expense components and gross profit.
- Recovers missing SG&A from matching selling and administrative components, cost of sales from revenue minus gross profit, and revenue from goods plus services.
- Requires the same issuer, annual period, filing vintage and currency for every identity.
- Preserves reported values and rejects conflicting components or negative derived costs.
- Saves refined data, recovered-observation provenance and before/after coverage in `Data/Fama and french/Refined/`.
- Leaves raw downloads and first-pass processed datasets unchanged.

## Original SEC filings online

Run `sec_filings.py` directly to attempt all missing company-year requests. This is a potentially long download, not a quick local recalculation. Use `--limit 24` for a bounded test.

- Downloads filing directories, original XBRL instances, labels and presentation structures.
- Preserves matched issuer contexts, annual periods, publication dates, currencies and source URLs.
- Maps exact custom labels only when they occur on a primary statement; uncertain custom concepts go into `Online/custom_concept_review.csv` without filling the core fields.
- Caches raw documents and successful parsed company-years. Restarting reuses completed work; separate batches retain previous online observations.
- Saves results and the before/after coverage report under `Data/Fama and french/Online/`.
- Leaves the original and offline-refined datasets unchanged.
