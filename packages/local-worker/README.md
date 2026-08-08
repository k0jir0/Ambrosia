# Ambrosia Local Worker

The local worker is the supported bridge between cloud-hosted Ambrosia and a
user's local Ollama. It makes outbound HTTPS requests only and calls Ollama on
loopback; no home-network port is exposed.

1. In Ambrosia, create a worker credential from the organization admin area.
2. Set `AMBROSIA_API_URL`, `AMBROSIA_WORKER_TOKEN`, and `OLLAMA_MODEL`.
3. Run `python packages/local-worker/ambrosia_local_worker.py`.

Use `--once` for a single claim attempt. A credential is shown once, is scoped
to one organization, and can be revoked independently. Model outputs remain
advisory and are catalogued with model digest, schema version, evidence hash,
token/timing metrics, verification status, and content hash.
