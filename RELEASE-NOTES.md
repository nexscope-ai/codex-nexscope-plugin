# 0.1.2.dev7 data Pre-release

This development preview exposes only the Apache-2.0 minimal data distribution.
It is published from `feature/343-data-prerelease`, tag `v0.1.2-dev.7-data`.
The repository default branch is not replaced or relicensed.

Included: data CLI; Amazon search/detail adapters; explicit browser-account and
environment-Key contexts; request planning/execution/cache isolation; complete
comparison workflow; free user-owned CSV/JSON comparison; HTML/CSV/Markdown
reports with evidence; environment diagnostics; minimal plugin and fictional samples.

Independent Skills are unchanged. No backend or website deployment is included.

## Verified before upload

- Allowlisted source hashes, Apache headers and third-party notices.
- Reproducible wheel builds with pinned build tooling.
- Fresh wheel installation outside the source checkout on Windows, Python 3.11
  and 3.14; offline and full dependency/mock checks; 84 regression tests per run.
- Paired minimal plugin archive and its exact embedded runtime/dependency hashes.
- Existing independent Skills remain unchanged; legacy API Key behavior is covered
  by mocks. Earlier dev7 upgrade/rollback checks passed; this preview does not migrate Skills.
- Static dependency/native-license review covers macOS/Linux targets. This does
  not establish successful native runtime or credential-store operation.

## Real acceptance still pending

1. macOS/Linux installation, native dependencies and credential-store integration.
2. Complete natural-language tasks in actual Codex/Claude plugin hosts.
3. Real browser connection/login, real search/details and service-side errors/credits.
4. Deployed registration -> effective call -> payment/refund attribution integration.
5. External 5–10-user pilot and post-publication acquisition/conversion observation.

These remain NOT_RUN; mock evidence is not a substitute. No real paid calls,
payments, refunds or deployments were performed. This early Pre-release is
authorized independently of those stable-release acceptance activities.

Install instructions, free offline workflow and rollback are in README.md.
Use release-manifest.json and SHA256SUMS to identify this exact release.
