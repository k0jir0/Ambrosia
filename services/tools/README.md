# MCP-Style Tool Adapters

Tools should be strict, narrow, and auditable. Do not expose broad database or filesystem access to agents.

Initial tool contracts:

- retrieve_prior_reviews
- retrieve_user_notes
- retrieve_source_pointers
- fetch_market_snapshot
- normalize_symbol_and_horizon
- generate_validation_specification
- check_validation_hygiene
- record_decision_state
- record_trial_count
- record_follow_up_outcome
- write_audit_event

All external content passed to tools is untrusted data, not instruction.