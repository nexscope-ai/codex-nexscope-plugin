# Nexscope data CLI — GitHub Pre-release

Copyright 2026 Nexscope. Licensed under [Apache-2.0](LICENSE).

Version **0.1.2.dev7**, tag **v0.1.2-dev.7-data**. This is a development
preview of the minimal data distribution, not a stable production release.
It compares user-owned CSV/JSON data and includes Amazon search/detail
adapters, planning, execution and source-checkable HTML, CSV and Markdown reports.

## Download and verify

Download assets from the [Pre-release](https://github.com/nexscope-ai/codex-nexscope-plugin/releases/tag/v0.1.2-dev.7-data).
The release includes the wheel, minimal plugin ZIP, matching source ZIP,
CSV template, fictional CSV/JSON examples, field descriptions and SHA256SUMS.
Verify each downloaded artifact against SHA256SUMS before installing:

```powershell
Get-FileHash ./nexscope_cli-0.1.2.dev7-py3-none-any.whl -Algorithm SHA256
```

On macOS use `shasum -a 256 <file>`; on Linux use `sha256sum <file>`.
Use a fresh Python 3.11+ virtual environment. Keep your old environment for rollback.

## Free offline comparison with your own data

In your new environment, install the downloaded wheel without fetching dependencies:

```text
python -m pip install --no-index --no-deps ./nexscope_cli-0.1.2.dev7-py3-none-any.whl
nexscope --version
nexscope report describe
nexscope report template --out products.csv
```

Fill the template with your own data, then generate a report:

```text
nexscope report compare --input products.csv --format markdown --out comparison.md
nexscope report compare --input products.csv --format html --out comparison.html
nexscope report compare --input products.csv --format csv --out comparison.csv
```

These commands require no account, key or network, and impose no three-product
limit on local files. Keep each report with its adjacent `.evidence` directory.
Use new output paths to preserve existing reports. Field descriptions and fictional
examples are also included in [CLI resources](https://github.com/nexscope-ai/codex-nexscope-plugin/tree/v0.1.2-dev.7-data/cli/nexscope_cli/resources).
Connecting to Nexscope to refresh data is optional; API usage may consume credits.

## Complete product-comparison demo

```text
nexscope workflow compare --asins B000000001,B000000003 --dry-run --max-calls 3
nexscope workflow compare --asins B000000001,B000000003 --execute --mock complete --format all --out comparison-demo
```

This uses fictional mock data. The output contains the plan, per-request evidence,
dataset and reports. It does not contact Nexscope. Keyword search and selected
ASIN workflows are also supported; run `nexscope workflow compare --help`.

## Minimal plugin and online dependencies

Extract `codex-nexscope-data-0.1.2.dev7.zip`. From the archive root, install the
paired runtime and hash-pinned platform dependencies into a dedicated environment:

```text
python -m pip install --isolated --index-url https://pypi.org/simple --require-hashes --find-links ./runtime -r ./runtime/requirements.txt
nexscope doctor --profile plugin
```

The archive contains `.codex-plugin/plugin.json` and `skills/nexscope/SKILL.md`.
Follow your assistant's local plugin-loading instructions. Full Codex/Claude host
acceptance remains pending; this release does not claim marketplace approval.
The source ZIP is for rebuilding, while the plugin ZIP includes the ready runtime.
Windows full dependency installation and mock flows have been verified. macOS/Linux
native installation and credential-store acceptance remain pending.

The plugin uses browser-account authentication and the OS credential store.
Explicit `env-api-key` integrations are separate, never a fallback for browser login.
Independent Skills retain their existing installation and `NEXSCOPE_API_KEY` use:
they do not require this CLI and are not migrated by this release.

## Verification and limitations

See [RELEASE-NOTES.md](https://github.com/nexscope-ai/codex-nexscope-plugin/blob/v0.1.2-dev.7-data/RELEASE-NOTES.md) for checks and unfinished real acceptance.
No production backend or webpage deployment, real paid API call, real payment/refund
or assistant model task was performed for this release. Do not interpret mock
success as live-service acceptance. API credits and service access are separate
from the open-source license.

## Rebuild and rollback

For a reproducible build, use Python 3.11+, setuptools 84.2.1 and
`SOURCE_DATE_EPOCH=1767225600`, then run `python -c "from setuptools.build_meta import build_wheel; build_wheel('dist')"`
from an extracted source ZIP. Build tooling is separate from runtime dependencies.
The release manifest records the source commit and artifact hashes. Automatic
GitHub source archives may have different ZIP bytes; use the attached source ZIP
for the recorded SHA256. For rollback, switch back to your previous environment
and matching plugin; do not overwrite existing Skill directories or delete user data.

## Scope and feedback

Apache-2.0 applies to this tag's minimal data tree: CLI, two adapters, report
templates, fictional examples and the minimal plugin entry. It does not relicense
other branches, earlier history, the commercial backend, website, other Skills
or business data. Third-party notices retain their original terms.

Report reproducible problems in [GitHub Issues](https://github.com/nexscope-ai/codex-nexscope-plugin/issues).
Include the version, OS, Python version and redacted error. Never post keys,
credentials or private business data.
