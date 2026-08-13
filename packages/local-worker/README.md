# Ambrosia Local Ollama Worker

The worker is the supported outbound-only bridge between cloud-hosted Ambrosia
and Ollama on the user's computer. It calls only an HTTPS Ambrosia API and an
Ollama endpoint bound to loopback. Never expose port 11434, use a public tunnel,
or put a worker credential in a command-line argument.

## Install and verify

Install Python 3.12 and Ollama, pull the model approved by the Ambrosia tenant,
and download the published worker ZIP plus its `.sha256` file. Verify the ZIP
before extracting it:

```powershell
$expected = (Get-Content .\ambrosia-local-worker.zip.sha256).Split(' ')[0]
$actual = (Get-FileHash .\ambrosia-local-worker.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'Ambrosia worker checksum mismatch' }
```

For a signed release, also verify `AmbrosiaLocalWorker.cat` with
`Get-AuthenticodeSignature` and `Test-FileCatalog` after extraction.

Release maintainers build the package with
`packages/local-worker/package-worker.ps1`. The script emits a deterministic
file manifest, ZIP checksum, and, when `-CertificateThumbprint` is provided, an
signed Windows file catalog covering the package. Production releases must be
signed by the release certificate; an unsigned development package is not a
production artifact.

## Enroll and run

1. As an organization owner or admin, create a worker in the Ambrosia admin
   page. Copy the one-time credential into the operating system's secret store.
2. Set the environment without placing secrets in shell history. The API URL
   must be HTTPS; the Ollama URL defaults to `http://127.0.0.1:11434` and any
   non-loopback URL is rejected.
3. Run the diagnostic, then start the worker:

```powershell
$env:AMBROSIA_API_URL = 'https://staging.example.com/api'
$env:AMBROSIA_WORKER_TOKEN = '<one-time worker credential>'
$env:OLLAMA_MODEL = 'approved-model:tag'
$env:OLLAMA_CONTEXT_LENGTH = '8192'
$env:OLLAMA_MAX_OUTPUT_TOKENS = '1536'
python .\ambrosia_local_worker.py --diagnose
python .\ambrosia_local_worker.py
```

For a persistent staging canary, use the signed package's installer from the
same Windows account that will run the worker. The installer prompts for the
one-time token as a `SecureString`, protects it with current-user Windows DPAPI,
registers a limited scheduled task at logon, and restarts failures with bounded
backoff. The credential is never placed in task arguments or the JSON config:

```powershell
.\install-scheduled-worker.ps1 `
  -ApiUrl 'https://staging.example.com/api' `
  -Model 'qwen3:8b-q4_K_M'
```

The task intentionally runs only for the installing user because another
account cannot decrypt that user's DPAPI secret. Stop and revoke the worker
before deleting `%LOCALAPPDATA%\Ambrosia\LocalWorker` during decommissioning.

`--diagnose` is the supported one-command health check. Version 3 does not treat
an installed manifest as readiness. It explicitly allocates the configured
context, executes schema-constrained analyst, verifier, repair, and final-verifier
generations, confirms the model remains loaded with the exact digest, and
authenticates the resulting `preflighted` capability with Ambrosia. It emits
machine-readable JSON containing the tested context, loaded size/VRAM placement,
stage hashes, durations, worker/Ollama versions, and capability digest. A model
that cannot allocate reports a bounded failure such as `out_of_memory` or
`model_load_failed` and is never advertised. `--once` performs one claim attempt
after the same mandatory preflight.

The advertised context is the context actually passed to Ollama through
`num_ctx`; it is not the model's theoretical maximum. Qualify a larger context
separately before changing `OLLAMA_CONTEXT_LENGTH`. The staging bridge currently
requires 8192 tokens, so a worker qualified only at 4096 will not claim its jobs.

Each structured generation disables the model's separate thinking trace because
the worker already implements explicit analyst and independent-verifier stages.
It also caps output with `OLLAMA_MAX_OUTPUT_TOKENS` (default 1536, hard bounds
256-4096). This prevents a thinking-capable model's otherwise unbounded output
from consuming the 15-minute operation deadline. Raising the cap requires a new
four-stage hardware preflight and latency qualification.

## Rotation, revocation, and recovery

Rotate a credential from the admin API or UI, stop the worker, replace the
secret-store value, rerun `--diagnose`, and restart it. The old token becomes
invalid immediately. Revoke the worker before decommissioning or whenever
compromise is suspected; a revoked worker cannot heartbeat or commit an
in-flight result.

The cache contains bounded, hash-addressed results only to survive a crash
between inference and upload. Successful upload deletes the corresponding
entry. Protect the cache with the user's filesystem permissions and delete it
when removing the worker. Server retention/deletion policy applies to queued
snapshots, runs, rejected outputs, dead-letter jobs, and audit records; the
worker does not independently archive prompts or completions.

Model outputs remain advisory. AWS revalidates model policy, schema, instrument,
cutoff, citations, calculation artifacts, prompt-injection policy, lease fence,
and packet version before any claim can enter a report.
