# Release claims register

Public language is limited to claims with an owner and reproducible evidence.
“Implemented” means code and automated tests exist; it does not mean AWS is
deployed, a control is independently certified, a model is accurate, or a
customer is willing to pay.

| Claim | Allowed wording | Evidence owner | Current evidence | Release state |
| --- | --- | --- | --- | --- |
| Human authority | “Models advise; a person records the decision.” | Product | Workflow code and journey tests | Implemented/tested |
| Private accounts | “Email/password accounts use private organization workspaces.” | Security | Argon2id identity, sessions, CSRF, tenant integration tests | Implemented; production deployment pending |
| Tenant isolation | “Application scoping and PostgreSQL RLS protect tenant-owned records.” | Security/DB | V0008 and adversarial tests | Implemented; independent review pending |
| Evidence provenance | “Packets retain source and as-of labels.” | Product/data | Packet schema and workflow tests | Implemented within supported workflow |
| AWS hosting | “Ambrosia is hosted on AWS.” | Platform | Terraform is not deployment evidence | **Forbidden until production cutover evidence passes** |
| Ollama quality | “Local Ollama improves disconfirmation quality.” | ML evaluation | Frozen suite only; no live baseline | **Forbidden until preregistered evaluation passes** |
| Security | “Secure,” “enterprise-grade,” or “compliant” | Security/legal | Internal controls are not certification | **Forbidden without scoped independent evidence and counsel approval** |
| Returns/alpha | Any performance, return, or alpha claim | Investment/legal | No prospective customer outcome evidence | **Forbidden** |
| Traction | Customer, retention, revenue, or willingness-to-pay claim | Finance | No verified cohort artifact in repository | **Forbidden until primary business evidence exists** |
| Investor value | “Ambrosia helps teams make traceable, challenged investment decisions.” | CEO/product | Golden workflow and observed user evidence | Product wording allowed; adoption/value inference requires pilot evidence |

Every screenshot and demo must label live, cached, simulated, or unavailable
data. The guided case is “dated illustrative sample,” never live market data.
Percent-complete statements are prohibited unless the denominator, owner,
measurement time, and evidence are visible. Backtests are research artifacts,
not return promises.

The release owner reviews this table and the public site at every cut. Any new
material statement starts as forbidden until its evidence owner updates the
register. Counsel approves regulated, privacy, security, and investment-related
language. Finance validates cohort, conversion, retention, revenue, pipeline,
and willingness-to-pay statements from primary records.

Supply-chain note: the March 2026 Trivy incident demonstrated that security
tools can become the attack path. New release actions are pinned to immutable
commits; the AWS workflow scans before push, emits SBOMs, signs image digests,
and deploys by digest. See the [official Trivy advisory](https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23) and [Sigstore cosign documentation](https://docs.sigstore.dev/cosign/signing/signing_with_containers/).
