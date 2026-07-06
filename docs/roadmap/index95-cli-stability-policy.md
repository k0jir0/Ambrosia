# Index95 Phase 6: CLI Stability Policy

## Versioning and Compatibility

- Command contracts follow semantic versioning aligned to CLI package versions.
- Major version changes may remove or rename commands.
- Minor version changes may add commands and optional flags.
- Patch version changes must not change required flags, payload shape, or exit-code behavior.

## Stability Classes

- Stable: expected for automation and CI usage; backward-compatible within major version.
- Preview: available but can evolve; not recommended for mission-critical automation.
- Internal: unsupported for external automation.

## Stable Command Surface (Current)

- `ambrosia auth *`
- `ambrosia config *`
- `ambrosia health *`
- `ambrosia reviews *`
- `ambrosia packets *`
- `ambrosia market snapshot`
- `ambrosia scanner run`
- `ambrosia jobs *`
- `ambrosia plans *`
- `ambrosia relay evaluate|scorecard|runs|get`
- `ambrosia signals create|list|get|writeback-decision|writeback-outcome|quality-scorecard`
- `ambrosia alpha create|list|decay`
- `ambrosia backtests run`
- `ambrosia paper-trades create|list`
- `ambrosia warm-path ingest|list`
- `ambrosia enterprise service-account|service-accounts|service-account-rotate|service-account-revoke|audit-export|sso-config|sso-get|offline-bundle|security-packet|readiness`
- `ambrosia commands list|show`

## Output and Exit Codes

- Exit `0`: success.
- Exit `1`: API or command error.
- `--json` output is canonical for automation.
- Human output may evolve, but `--json` key semantics remain stable in a major release line.

## Compatibility Gates

- Unit contract tests: `packages/cli/tests/test_cli_contract.py`.
- Multi-OS workflow: `.github/workflows/cli-compatibility.yml`.
- SDK/CLI transcript verification: `scripts/verify-sdk-cli.py`.

## Deprecation Policy

- Deprecated command/flag paths receive one minor release cycle warning before removal.
- Removals require changelog note and command migration guidance.
