# Nexscope Codex plugin

Ecommerce research in Codex with [Nexscope](https://www.nexscope.ai). Research products, keywords, markets, competitors, reviews, and advertising, then save the results as files.

The repository root is the plugin root. Codex discovers the Nexscope Skill in `skills/`.

## Skill

| Skill | Purpose |
| --- | --- |
| `nexscope` | Connects your Nexscope account, selects the relevant research workflow, retrieves ecommerce data, and exports results. |

The Skill uses the Nexscope CLI to discover the available workflows and their usage instructions:

```sh
nexscope get-skills core
```

## Product comparison companion (local candidate)

The original natural-language Nexscope Skill now routes product comparisons to
the independent CLI's shared `get-skills product-comparison` guide and
`nexscope_cli.workflows.compare`. Other research routes keep the original CLI.
This checkout/ZIP is a candidate; it has not updated a published Codex or Claude
plugin. The MCP canvas plugin is a separate product.

Both distributions are named `nexscope-cli`, import `nexscope_cli`, expose
`nexscope`, and report version `0.1.1`. Do not replace one with the other globally.
The original proprietary wheel remains at `runtime/nexscope_cli-0.1.1-py3-none-any.whl`;
the Apache-2.0 companion wheel is under `runtime/companion/`. Its exact official
artifact is pinned in [.codex-plugin/companion.json](.codex-plugin/companion.json):

- Source: `nexscope-ai/nexscope-cli`, revision `b78bcf460113eacdfa5af2f5d5489d4ad8665254`.
- Wheel SHA-256: `38220114193b886af2fafcd282db1cfe2f1cd0606afb74e60f76fd9dabf5e114`.
- Package metadata license: `Apache-2.0`; its own LICENSE/NOTICE and third-party
  notices stay inside that wheel. The plugin and its private Skill resources
  remain proprietary; none are copied into the Apache package.

After extracting the complete candidate ZIP, explicitly install the companion
offline using Python 3.11+ and an already-installed `uv`:

```sh
python -I /absolute/plugin/scripts/install_companion.py --wheelhouse /absolute/plugin/runtime/companion/wheels
python -I /absolute/plugin/scripts/companion.py --verify-companion
python -I /absolute/plugin/scripts/companion.py get-skills product-comparison
python -I /absolute/plugin/scripts/companion.py workflow compare --asins B000000001,B000000002,B000000003 --dry-run
```

The candidate includes dependency wheels for **Windows x64, CPython 3.12**.
Other Python/platform combinations need an explicit offline wheelhouse matching
`nexscope_cli/dependencies.lock` inside the pinned wheel. Setup uses only that
wheelhouse with hash checking and no index/network. It never downloads an
installer, replaces a global command, activates an environment, or touches the
existing keyring. Missing/incompatible dependencies fail closed.

The launcher always chooses the absolute Python inside this plugin's
`runtime/companion/.venv`, checks the pinned wheel and every installed package
file before import, and uses isolated Python mode. Keep using it for auth,
account and comparison commands; do not replace it with a global `nexscope`.
Codex connection creation declares `codex-plugin/marketplace/plugin`; Claude
guidance uses `auth login --source-client claude-code --source-channel
marketplace --source-entrypoint plugin`. The authoritative Claude publication
repository remains unresolved; no live Claude plugin update is claimed.

Read the returned guide for direct ASINs, keyword candidates and `--resume`,
partial results, and free CSV/JSON input reports. Show the exact scope and
remaining cumulative request budget before any paid stage and obtain explicit
authorization; `--max-calls` is not a monetary cap. Never retry an uncertain paid
request automatically. Mock examples use fictional products.

For rollback, stop comparison commands and return other research to the original
entry. Preserve the companion environment before explicitly replacing it; setup
refuses an existing `.venv`. Restore the reviewed prior companion wheel/manifest
and install into a fresh scoped environment if needed. Existing reports and OS
keyring records remain in place; do not delete or migrate them. Old `run`,
`get-skills`, parameters and raw JSON/report readers are unchanged.

Local verification uses `scripts/self_check.py` with the scoped Python after
offline setup (it supplies the existing legacy test's `requests` prerequisite).
Build with `python scripts/build_plugin.py`; the output is
`dist/codex-nexscope-plugin-0.1.1-companion-candidate.zip`. No installed venv is
included, and the existing `codex-nexscope-plugin-0.1.1.zip` is not overwritten.

## Original CLI requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An OS credential store: macOS Keychain, Windows Credential Manager, or Linux Secret Service/KWallet
- A Nexscope account with credits for paid API requests

Install the CLI from this repository:

```sh
git clone https://github.com/nexscope-ai/codex-nexscope-plugin.git
cd codex-nexscope-plugin
uv tool install .
nexscope --version
```

## Usage

With the plugin installed in Codex, select Nexscope and describe your task:

> Find Amazon US wireless headphones and save the results as a CSV.

> Compare keywords for these Amazon competitor ASINs.

> Analyze the market for insulated water bottles.

When a connection is needed, Codex provides a Nexscope link. Open it, sign in or register, and confirm the connection. Return to the conversation and reply **done** to continue. Credentials are stored in your OS credential store; you do not need to paste an API key into chat.

If credits run out, Codex provides a recharge link and checks your balance when you return.

## Repository contents

- `.codex-plugin/` — plugin metadata
- `skills/` — Codex Skill instructions
- `assets/` — plugin icon
- `cli/` — Nexscope CLI and research resources
- `scripts/` — packaging and validation tools

## License

Proprietary — see [LICENSE](LICENSE). Use is subject to Nexscope's applicable service terms.
