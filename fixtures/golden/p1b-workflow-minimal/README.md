# P1b Workflow Minimal Fixture

P1b は P0b QEG bundle と P1a trust artifacts を、RanD / Shipyard-cp /
workflow-cookbook へ渡せる advisory artifact へ写像する。

この fixture は意図的に `risk-db-high` の missing execution gap を含むため、
`workflow_status=conditional` と `accepted_with_gaps` が期待値である。
HATE は RanD verdict、Shipyard publish approval、workflow-cookbook checker を
上書きしない。
