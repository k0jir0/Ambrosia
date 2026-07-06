# Ambrosia Hot Path (Rust)

This service is the separate deterministic hot-path boundary for low-latency order gating.
It is intentionally isolated from the Python API and any LLM logic.

## Why Rust for hot path

- Predictable latency and memory safety without garbage-collector pauses.
- Strong type system for risk-control invariants.
- Competitive runtime performance close to C++ for this workload.
- Easier operational safety for a small team versus C++ UB footguns.

## Protocol

The service listens on `HOTPATH_BIND` (default `127.0.0.1:9100`) and accepts line-delimited JSON commands.

Supported commands:

- `Health`
- `KillSwitch`
- `NewOrder`

`NewOrder` runs deterministic pre-trade checks:

- kill switch status
- basic field validity
- side and symbol policy
- max notional limit
- optional price collar via `referencePrice` and `maxSlippageBps`
- strategy-origin hard reject when payload indicates LLM/model-generated routing

No external calls are done in the decision loop.
The in-path logic is deterministic and contains no LLM or remote inference hooks.

## Run

```bash
cd services/hotpath-rs
cargo run --release
```

## Example

Send a health probe:

```bash
echo '{"type":"health"}' | nc 127.0.0.1 9100
```

Enable kill switch:

```bash
echo '{"type":"killSwitch","enabled":true}' | nc 127.0.0.1 9100
```

## Scope note

This is a production-aligned scaffold for the hot path service boundary.
It does not yet include exchange adapters, wire protocols, co-location, PTP time sync,
or conformance test packs.
