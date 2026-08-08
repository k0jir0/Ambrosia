# Documentation authority

Current release authority lives in `docs/operations/`:

- `INDEX132_IMPLEMENTATION_LEDGER.md` — repository implementation and verified gates.
- `RELEASE_CLAIMS_REGISTER.md` — allowed and forbidden product/investor wording.
- `AWS_MIGRATION_RUNBOOK.md` — staging, rehearsal, cutover, and rollback procedure.
- `PRODUCTION_STANDARD.md` and `THREAT_MODEL.md` — production and security boundaries.
- `index132-external-evidence.template.json` — external proof required for a GO decision.

Most uppercase milestone, completion, deployment, pitch, and session files in
this directory predate Index132. They are historical planning records, not
current deployment, security, customer, performance, or completion evidence.
Their URLs, percentages, checkmarks, and future-tense actions must not be copied
into a release, website, diligence room, investor deck, or customer claim
without revalidation under the claims register.

The machine-readable authority is generated with:

```powershell
python scripts/generate-index132-readiness.py
```

`NO_GO` is expected until independently observable external gates close.
