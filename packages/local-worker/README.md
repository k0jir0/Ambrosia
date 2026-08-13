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
python .\ambrosia_local_worker.py --diagnose
python .\ambrosia_local_worker.py
```

`--diagnose` is the supported one-command health check. It verifies configuration,
loopback Ollama connectivity, the installed model's immutable digest, Ollama
version, and cache location, and emits machine-readable JSON. `--once` performs
one claim attempt for supervised testing.

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
