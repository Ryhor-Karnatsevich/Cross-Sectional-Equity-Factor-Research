# Fama-French Research

A separate research path for size, value, operating profitability and investment characteristics. The existing price-volume research pipelines remain unchanged.

Current task: assemble historical company fundamentals and market capitalization before constructing portfolios.

- Reuse existing stock returns and point-in-time membership.
- Start from the complete historical security union, including former index members.
- Map securities to company identifiers; different tickers can share one issuer's financial statements.
- Collect annual assets, book-equity components, revenue, cost of goods sold, SG&A and interest expense.
- Keep fiscal-period dates, publication dates, reporting currency, units and source identifiers.
- Obtain historical market capitalization, or unadjusted prices and historical shares outstanding.
- Include at least two preceding fiscal years for the first annual portfolio formation, where available.
- Apply membership and data-availability rules on each formation/evaluation date.

An S&P 500 implementation tests Fama-French-style characteristics within that universe. It does not replicate the original broad-US-market factors exactly.

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
