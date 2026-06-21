# Workflow Layer

The MVP uses a deterministic review generator while the product artifact stabilizes. The intended LangGraph workflow is:

1. Intake normalizer
2. Retrieval node
3. Thesis generator
4. Heterogeneous adversary
5. Validation-spec gate
6. Tradeability reviewer
7. Judge and editor
8. Memory writer

The API contract should not change when the deterministic generator is replaced by LangGraph.

Required workflow metadata:

- `workflow_version`
- `workflow_run_id`
- step status
- idempotency key
- audit events
- model and prompt versions