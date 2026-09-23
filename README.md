# codex-nexscope-plugin

A readable Codex skill and an independent Nexscope CLI. The CLI bundles 138 ecommerce skill resource sets (136 routable, 2 unavailable pending upstream dependencies) from `nexscope-ai/nexscope-ecommerce-skills` at `cd532d33ce21a643f9945e05ca556b5ba890813d`. It does not use the commercial Amazon plugin's authorization or encrypted runtime.

## Install locally

Python 3.11+ and a supported OS keyring are required (macOS Keychain, Windows Credential Manager, Linux Secret Service/KWallet). No plaintext credential fallback is used.

```sh
git clone https://github.com/nexscope-ai/codex-nexscope-plugin.git
cd codex-nexscope-plugin
uv tool install .
nexscope --version
nexscope get-skills core
nexscope auth login
# Follow the printed webpage link, confirm, return to Codex and reply done.
nexscope auth poll
nexscope get-skills amazon-search
nexscope run amazon-search -- '{"keyword":"wireless headphones"}'
```

Use the exact parameters from the selected skill; the example is not a guarantee that every provider accepts `keyword`. The bundled wheel avoids depending on an unpublished PyPI package. Build it with `python3 scripts/build_plugin.py`. Local development: `uv tool install .`.

Install the plugin directory or resulting ZIP using Codex's plugin installation workflow. The runtime wheel is inside the ZIP. No MCP server is required. Dependencies are installed from the configured Python package index.

## Connection and payment

The website uses `/cli/connect?session=...` for login/registration and explicit confirmation. A private poll secret stays in the OS keyring, never the URL or chat. The CLI saves the returned API key before acknowledging receipt. Requests expire after one hour. `auth logout` revokes this CLI key; other plugin credentials remain independent.

`nexscope account` returns the credit balance and account-bound recharge URL. After checkout, `/cli/recharge` checks the real order status. Return to Codex and check the balance before resuming. The CLI wrapper never automatically replays a script after a failure. Each run uses a fresh output directory to prevent cross-account or stale cached responses.

The backend and web changes must be deployed before live login works. Backend `cli.web-origin` must equal the public website origin (including scheme and port). Payment return configuration must point at that same website. For a local backend, use `nexscope --api-base http://127.0.0.1:8080 auth login`; credentials are isolated per origin.

## Verify and package

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python scripts/self_check.py
python3 scripts/build_plugin.py
```

`catalog.json` records every packaged resource digest and the upstream source revision. English localization is applied during sync, with request wire enums preserved through JSON Unicode escapes. To update, review a source checkout and run `python3 scripts/sync_skills.py /path/to/checkout`, then repeat checks. A package update is required to change bundled executable code.

The backend mock check, web browser check, real OAuth callbacks, Redis concurrency and payment sandbox verification are separate from CLI offline checks. Public registry publication and official marketplace submission have not been performed. See `SUBMISSION.md`.

## Local implementation verification

Verified locally: backend Maven compilation; executable Java mock checks for request ownership, origin, repeated/concurrent polling, acknowledgment, expiry, denial, zero credits and revocation; CLI offline handoff, loopback HTTP, redirect denial, real bundled-script credit error without replay, CSV and all 138 resource digests; web browser checks with mocked APIs; 25 existing auth/billing tests; changed-file ESLint; plugin and skill validation; wheel/ZIP generation.

Full web TypeScript checking is blocked by existing unrelated test typing and missing GPT image assets. No errors were reported in changed files. Real OAuth, Redis/MySQL fault behavior and payment-provider callbacks are not certified by mocks. Backend deployment, package-registry publication and official marketplace submission remain separate release steps.


## Unavailable upstream workflows

`get-skills core` separates runnable catalog entries from unavailable workflows. `geo-score-check` lacks its upstream scorer and scoring references; `product-ai-visibility` depends on a separate model gateway and workspace setup. `get-skills <name>` explains these prerequisites without emitting nonportable upstream instructions, and `run` refuses them before reading credentials or executing scripts. These are not counted as runnable migrations. Restore the missing resources/integration and verify the workflow before removing its entry in `scripts/skill_availability.json`.

If `auth logout` cannot confirm server-side revocation, it fails and retains the local credential. Retry after the dependency recovers, or revoke the key through Nexscope API Access. A network/authentication error is not reported as successful revocation.


## Publication checks

Run `python3 scripts/check_publication.py` and `python3 scripts/self_check.py` before committing. If Gitleaks is available, also run `gitleaks dir . --config .gitleaks.toml --redact`. The only scan exemption covers generated SHA-256 catalog entries, which the self-check verifies against actual file contents. Never commit credentials, local environments, run outputs or environment files.
