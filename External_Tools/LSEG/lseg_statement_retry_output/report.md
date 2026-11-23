# Single-company retries of failed LSEG statement batches

- Finished plan: True
- Original failed batches: 155
- Single-RIC jobs: 2861
- Jobs processed this run: 2861
- New SDK calls invoked: 2901
- Statement rows parsed: 311859
- Elapsed: 00:41:39

| Status | Jobs |
|---|---:|
| PARSED | 2595 |
| NO_MATCHING_STATEMENT_ROWS | 229 |
| REQUEST_ERROR | 37 |

Only universes from the original failed whole-statement batches are queried.
Fields and parameters are unchanged; each call now has one RIC.
No old output folders are required. No unrelated extraction stage or price download runs.
statement_rows.csv contains amounts/text and FY request labels. Actual period ends and publication dates are not fabricated.
field_definitions.csv contains the exact full provider definitions referenced by definition_id.
All rows are review candidates, not approved Fama-French inputs. A role hint is not an equivalence decision.
The compressed raw-response cache preserves original table columns and values.
Repeat this command to resume; failed calls are retried, successful/empty replies reused. --retry-empty rechecks empty replies.
