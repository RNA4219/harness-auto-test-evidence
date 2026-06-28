# HATE-P1B-005 Shipyard No-Overwrite Fixture

This fixture intentionally contains Shipyard-looking enforce and publish approval
signals. P1b must preserve them as input refs only. HATE must never set
`publish_gate_override`, `release_gate_override`, or `shipyard_state_override`.
