# Shared Schemas

The implementation should preserve these versioned schemas across frontend and backend:

- `review.v1`
- `claim.v1`
- `source_pointer.v1`
- `validation_spec.v1`
- `tradeability_question.v1`
- `audit_event.v1`
- `packet.v1` (including typed provenance, disconfirmation, risk-gate, memory, and workflow status contracts)
- `mobile-control-plane.v1`

Version fields must be persisted so old decision memory remains interpretable after schema changes.
