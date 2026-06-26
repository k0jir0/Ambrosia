# Admin Boundary Rules

This document defines the boundary between user-safe, advanced, team, and admin surfaces.

## Exposure classes

- user: default end-user routes and actions.
- advanced: power-user/operator routes that are non-destructive but high-context.
- team: collaboration and shared workflow controls.
- admin: privileged operational controls and governance policy actions.
- internal-only: backend-only hooks not meant for direct user interaction.

## Route boundary policy

- /admin is required for privileged controls.
- /team is required for shared collaboration controls.
- /advanced is required for operator and instrumentation controls.
- No non-internal backend function should exist without a visible route mapping.

## Admin controls must include

- Clear warning labels for privileged operations.
- Audit event capture for all write operations.
- Role-based access checks at route and action level.
- Explicit fallback and degraded-state disclosure.

## Change control

- Any new backend route must be classified by exposure class.
- Any new admin-capable route must be reflected in the visibility matrix.
- Visibility matrix rows must include required role and audit event metadata.
- CI visibility check must pass before merge.
