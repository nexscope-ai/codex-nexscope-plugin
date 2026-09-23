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

## Requirements

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
