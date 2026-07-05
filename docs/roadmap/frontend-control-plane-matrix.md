# Frontend Control Plane Matrix

| Route | Page | Primary Action | Required States | Evidence | keyboard-only | Web Vitals | audit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | `apps/web/src/app/page.tsx` | Open dashboard | loading, empty, stale, degraded, fallback, forbidden, success | Dashboard summaries | yes | monitored | route inventory sync |
| `/review/new` | `apps/web/src/app/review/new/page.tsx` | Create review | loading, empty, stale, degraded, fallback, forbidden, success | Review create flow | yes | monitored | review create events |
| `/review/[id]` | `apps/web/src/app/review/[id]/page.tsx` | Run decision workbench | loading, empty, stale, degraded, fallback, forbidden, success | Packet/workbench state | yes | monitored | packet audit trail |
| `/history` | `apps/web/src/app/history/page.tsx` | Inspect prior reviews | loading, empty, stale, degraded, fallback, forbidden, success | Review archive list | yes | monitored | history reads |
| `/markets/[ticker]` | `apps/web/src/app/markets/[ticker]/page.tsx` | Inspect ticker context | loading, empty, stale, degraded, fallback, forbidden, success | Market snapshot | yes | monitored | market refresh events |
| `/calibration` | `apps/web/src/app/calibration/page.tsx` | Review calibration metrics | loading, empty, stale, degraded, fallback, forbidden, success | Calibration panel | yes | monitored | scorecard audit |
| `/advanced` | `apps/web/src/app/advanced/page.tsx` | Operate advanced controls | loading, empty, stale, degraded, fallback, forbidden, success | Advanced panel inventory | yes | monitored | operator actions |
| `/admin` | `apps/web/src/app/admin/page.tsx` | View admin monitoring | loading, empty, stale, degraded, fallback, forbidden, success | Admin health tiles | yes | monitored | admin audit stream |
| `/governance/team-management` | `apps/web/src/app/governance/team-management/page.tsx` | Manage team governance | loading, empty, stale, degraded, fallback, forbidden, success | Governance matrix | yes | monitored | RBAC change log |
| `/discovery` | `apps/web/src/app/discovery/page.tsx` | Run discovery scans | loading, empty, stale, degraded, fallback, forbidden, success | Discovery results | yes | monitored | scan audit |
| `/reports/export` | `apps/web/src/app/reports/export/page.tsx` | Export reports | loading, empty, stale, degraded, fallback, forbidden, success | Export artifacts | yes | monitored | export audit |
| `/platform` | `apps/web/src/app/platform/page.tsx` | Inspect platform status | loading, empty, stale, degraded, fallback, forbidden, success | Health and phase summaries | yes | monitored | platform status reads |
| `/alpha` | `apps/web/src/app/alpha/page.tsx` | Inspect hypothesis and signals | loading, empty, stale, degraded, fallback, forbidden, success | Alpha/signal lists | yes | monitored | alpha read audit |
| `/execution-intelligence` | `apps/web/src/app/execution-intelligence/page.tsx` | Inspect warm-path operations | loading, empty, stale, degraded, fallback, forbidden, success | Warm-path event list | yes | monitored | execution event reads |
| `/relay-benchmarks` | `apps/web/src/app/relay-benchmarks/page.tsx` | Inspect relay benchmark posture | loading, empty, stale, degraded, fallback, forbidden, success | Relay scorecard | yes | monitored | relay read audit |
| `/enterprise` | `apps/web/src/app/enterprise/page.tsx` | Inspect enterprise readiness | loading, empty, stale, degraded, fallback, forbidden, success | Readiness and security packet | yes | monitored | enterprise readiness reads |
| `/cli-design` | `apps/web/src/app/cli-design/page.tsx` | Inspect CLI architecture | loading, empty, stale, degraded, fallback, forbidden, success | CLI design pillars and command families | yes | monitored | docs/control-plane read |
