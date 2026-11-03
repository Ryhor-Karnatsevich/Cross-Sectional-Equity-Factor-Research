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
