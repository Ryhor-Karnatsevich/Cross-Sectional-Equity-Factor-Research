# S&P500 factor study: declared construction rules

Version: `sp500_ff_v1`. Defined on 23 November 2026 after the input-coverage audit,
before running this research path's portfolio models. These are study choices,
not a claim of preregistration or exact replication of the French data library.
The machine-readable settings are in `model_config.py`; extraction settings
remain in `config.py`. No existing project pipeline imports the new settings yet.

## Research question and period

Do size, value, profitability, investment and momentum characteristics within
historical S&P500 membership help explain returns within the same universe?

Use July 2009 through June 2026: 204 calendar months before missing-return
exclusions. This includes complete July-to-June formation cycles and allows the
same intended period for FF3, Carhart4 and FF5. The earlier coverage audit does
not guarantee 204 valid factor-return observations under all construction rules.

Use historical membership, including former constituents, rather than today's
constituents. Never require a company to survive until the end of the sample.
The size comparison is between smaller and larger S&P500 companies. S&P500
breakpoints replace the original methodology's NYSE breakpoints intentionally.

## Book equity and accounting characteristics

**Book equity**

- Use the accepted `common_equity` amount in USD for the last annual fiscal
  period ending in the preceding calendar year.
- Require book equity to be positive for book-to-market and profitability.
- Common equity already excludes preferred equity: do not subtract it again.
- Do not substitute total or parent equity when preferred/minority adjustments
  are unavailable. Do not infer that missing preferred equity is zero.
- Do not add deferred tax balances. French's data-library update excludes this
  addition for fiscal years ending in 1993 or later; all study years are later.
- This is a provider-based common-equity implementation, not a full recreation
  of the Compustat/Moody's preferred-stock valuation hierarchy.

**Book-to-market**

`B/M = book equity for fiscal year ending in t-1 / market cap at December t-1 end`.
Use positive accepted capitalization from the actual required month end.

**Operating profitability**

`OP = (revenue - cost of sales - SG&A - interest expense) / book equity`.

Require all four income fields and book equity for the same issuer and exact
annual fiscal end, with all necessary publications available at formation.
Retain genuine negative reported expenses. Missing expenses remain missing;
partial expense fields never replace totals.

This uses the original-paper book-equity-only denominator consistently. The
current French library changed its denominator to book equity plus minority
interest in 2018. We do not mix those two conventions through time or silently
replace missing minority interest with zero. Requiring every expense field is
also stricter than French's published eligibility description (at least one).

**Investment**

`INV = assets for fiscal year ending in t-1 / assets for fiscal year ending in t-2 - 1`.

Require both asset values to be positive and their actual fiscal ends to be
330–400 days apart. Do not fill a missing year with an older statement.

**Momentum**

For holding month `t`, compound monthly returns from `t-12` through `t-2`,
inclusive. Skip `t-1`. This needs month-end prices from `t-13` through `t-2`.
Require all these observed month ends, valid price quality and capitalization
at the end of `t-1`. Form the momentum groups monthly.

## Information available at formation

Annual groups are formed at the last June trading close and first earn returns
in the following session. A date-only publication becomes usable one calendar
day after its publication date. It must be available by that June close.

Read accepted vintage records from `Consolidated/observations_all.parquet` and
select the latest accepted vintage actually known by the formation cutoff.
For identical publication dates, prefer SEC accession evidence over LSEG and
apply the accepted exact-concept priority; conflicting equal-priority amounts
must fail that characteristic. Never use a later filing to rewrite a past sort.
The selected matrices are convenient views, not complete historical as-of joins.

Use the last eligible fiscal end in the preceding calendar year. Join income
fields and equity on the same exact fiscal end. Accounting data are annual;
their availability dates, rather than fiscal-end dates, govern their use.
LSEG's original-report requests remain vendor-vintage evidence, not independent
certification of a point-in-time database.

## Eligible companies and share classes

Do not force every sort to use the approximately 300-stock joint-complete subset.

- Size/value uses positive book equity and December/June capitalizations.
- Size/profitability uses its complete annual income fields, positive book equity
  and June capitalization.
- Size/investment uses two consecutive annual asset values and June capitalization.
- Size/momentum uses its price history and previous month-end capitalization.
- The market portfolio does not require accounting statements.

At each formation, include only S&P500 members whose membership is already
observable. Handle company-level capitalization once per issuer, using accepted
CIK links or an explicit verified same-issuer crosswalk. Exclude and report a
security if the necessary issuer link remains unavailable; do not guess it from
a similar name or carry a predecessor's accounts across an unverified merger.

For multiple eligible share classes of one issuer, choose the class with the
highest mean valid dollar volume in the trailing 60 sessions (at least 20 valid
sessions). Break ties by ticker. If no class has that history, choose the first
eligible ticker alphabetically. Freeze the representative until the next sort,
apart from verified direct renames. No future liquidity or returns enter this
choice. Aggregate issuer evidence before applying the one-issuer rule.

## Sorting

Within each sort family's eligible S&P500 issuers:

1. Split size at the median capitalization.
2. Independently split the characteristic at its 30th and 70th percentiles.
3. Intersect the two assignments to create six portfolios.

Use linear quantile interpolation. Values equal to the median go to Small.
Characteristic values at the 30th percentile go to Low; values above that and
at the 70th percentile go to Middle; the remainder go to High. Do not force tied
values into different groups to make group sizes equal. An empty required group
produces a missing factor month, not a fabricated return.

Annual value, profitability and investment assignments remain fixed until the
next June formation. Momentum is sorted again at each month end. No winsorization,
z-scoring, sector neutralization or return-driven parameter selection is applied.
Report constituent counts, maximum weight, HHI and effective constituent count;
do not impose an invented statistical pass threshold on these diagnostics.

## Weights, membership changes and missing returns

At each month end, normalize positive, observed company capitalizations within
each existing group to set next month's weights. If capitalization is missing,
exclude that issuer at this ex-ante reset and report it. Do not forward-fill a
stale capitalization. Weights subsequently drift with realized total returns.

Use the existing adjusted-price total-return proxies after their price-quality
mask. Compute each leg's monthly total return by compounding its daily returns;
then subtract monthly leg returns. Do not compound a daily long-short spread as
if it were a fully funded long-only portfolio.

Closing-price data imply closing execution. Membership observed at close `d`
affects positions from the following session. Include the old position's return
through its executable exit close, rather than retrospectively deleting it.
Liquidate an exiting issuer at that close and keep its proceeds in risk-free
cash until the next monthly reset. Annual characteristic groups admit newly
added index members only at the next June sort; monthly momentum and market
portfolios can admit them at their next monthly reset. This closing-execution
convention can include an exit-day return after the index's effective removal.

If an already-held stock's return or executable exit price is unavailable, mark
the affected leg/month missing and report the stock and pre-existing weight.
Do not treat it as zero, remove the loser after observing the outcome or silently
redistribute its weight to stocks with data. Use a terminal payout only when an
explicit verified total return/payout is available. Delisting-return coverage
therefore remains a limitation, even after issuer-data acceptance.

Primary factor returns are gross research returns. Transaction costs, stock
borrow, financing and implementation profits are outside this initial model
comparison. Equal-weight averaging of portfolio legs is distinct from the
capitalization weighting of stocks inside each leg.

## Factor definitions and comparison

Within each relevant six-portfolio family:

- `SMB_BM`: average Small value/neutral/growth return minus average Big return.
- `HML`: average Small/Big high B/M return minus average Small/Big low B/M return.
- `SMB_OP`: average Small profitability-group return minus average Big return.
- `RMW`: average robust return minus average weak return across the size groups.
- `SMB_INV`: average Small investment-group return minus average Big return.
- `CMA`: average conservative return minus average aggressive return across size groups.
- `SMB_5 = (SMB_BM + SMB_OP + SMB_INV) / 3`.
- `MOM`: average winner return minus average loser return across size groups.

Use the same S&P500 value-weighted market return and RF series for every model.
Construct the market independently of accounting availability, with the same
issuer, observed capitalization, membership lag and missing-held-return rules.
Use the French library's monthly RF in decimal units. The local DGS3MO series is
an annualized three-month yield, not the same monthly risk-free return; it is not
an automatic substitute. The small RF input still needs to be acquired by the
future builder; defining this methodology does not download it.

- `FF3_SP500`: market excess return, `SMB_BM`, `HML`.
- `CARHART4_SP500`: FF3 plus `MOM`.
- `FF5_SP500`: market excess return, `SMB_5`, `HML`, `RMW`, `CMA`.

FF3 and FF5 use different SMB definitions, so do not describe this pair as
strictly nested regressions. Compare the same test assets/portfolios over the
intersection of valid monthly observations. Do not select a different historical
period or stock sample separately for whichever model performs best.

## Source definitions and declared adaptations

- [French: size and book-to-market construction](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/six_portfolios.html).
- [French: five-factor definitions](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html).
- [French: investment construction](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/six_portfolios_me_inv.html).
- [French: monthly momentum construction](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html).
- [French: definition updates, including deferred tax and minority interest](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).

The restricted universe, S&P500 breakpoints, accepted provider common equity,
strict expense completeness, issuer representative choice, monthly cap resets,
closing-execution membership treatment and return-data limitations must be
reported with the model results. They are fixed research choices, not evidence
that the resulting factor returns will match the published series or earn alpha.
