# All-fronts LSEG completion

- Version: `2026-11-18-all-fronts-v1`
- Finished plan: True
- Mapped historical ticker labels: 884
- Missing candidate company-years before: 3183
- Candidate company-years found: 43
- New primary-field observations: 1247
- Additional source candidates: 3371
- Separate identity-review observations: 27904
- Returned template rows: 1926
- Derived COGS candidates (not source observations): 189
- Identity conflicts remain unapproved: WFT, XOM

## Fronts

Identifiers and ISINs: identifier_recovery.csv, identity_investigation.csv, identity_candidate_observations.csv.
Annual amounts: annual_gap_plan.csv, observations.csv, gap_outcomes.csv.
Whole statements and industry-specific definitions: template_capabilities.csv, statement_rows.csv, field_definitions.csv.
Publication-period issues: publication_review_before.csv, publication_review_after.csv. Adjacent FY labels are queried; Orig is kept.
Reconstruction: derived_cost_candidates.csv; requested currency/state and exact period must match; conflicts prevent calculation.
Month-end capitalization: strict_market_plan.csv, using the embedded project trading calendar, without seven-day tolerance.
Requests, errors and cache sources: fronts_report.csv, request_report.csv, recovery_raw.sqlite.

## Interpretation

No percentage of FF eligibility is inferred from response counts. Missing expenses are not zero.
A numeric alternative, gross-profit calculation, or unchanged current identity is not an approved historical FF input.
No template date is fabricated from its FY label. Discovered fields are separately requested with their own period dates.
Late publication remains a limitation when no timely original is returned; no unsupported as-of parameter or restated fallback is invented.
When whole templates are unavailable, template_capabilities.csv records the attempted requests; documented direct fields still run.
Financial/industry templates provide context, not proof that an absent COGS entry is zero or not applicable.
Identity-review observations and calculated candidates are excluded from combined_observations_candidate.csv.
All input folders are read-only. Re-run the same command to resume; --retry-empty rechecks empty replies.
