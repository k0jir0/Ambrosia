# Index95 Phase 6: Enterprise Packaging and Reproducible Install Patterns

## Goals

- Deterministic installs for CI and on-prem environments.
- Repeatable wheel builds with checksum verification.
- No implicit dependency drift during deployment.

## Pattern A: Reproducible Local Wheel Install (Linux/macOS)

Use script:

```bash
bash scripts/install-cli-reproducible.sh
```

What it does:

- Builds SDK and CLI wheels.
- Computes SHA256 checksums.
- Installs exact wheel artifacts (no index lookup required).
- Validates CLI availability via `ambrosia --help`.

## Pattern B: Reproducible Local Wheel Install (Windows)

Use script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-cli-reproducible.ps1
```

What it does:

- Creates deterministic wheel outputs.
- Emits checksums.
- Installs exact local wheels.
- Verifies command invocation.

## Pattern C: Air-Gapped / On-Prem Bundle

- Build artifacts in connected environment.
- Export:
  - `packages/sdk-python/dist/*.whl`
  - `packages/cli/dist/*.whl`
  - `artifacts/release-checksums.sha256`
- Transfer artifacts to restricted environment.
- Verify checksums before install.
- Install from local file paths only.

## CI Guidance

- Use pinned Python version.
- Install from built wheel path, not floating package index names.
- Keep checksum artifact in build evidence.
- Fail pipeline when checksum mismatch occurs.

## Related Artifacts

- `.github/workflows/release-cli-sdk.yml`
- `.github/workflows/cli-compatibility.yml`
- `artifacts/release-checksums.sha256`
