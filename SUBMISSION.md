# Release prerequisites

- This companion candidate is not a publication. Use the distinct
  `codex-nexscope-plugin-0.1.1-companion-candidate.zip`; do not overwrite a released
  same-name/version package. Review/publisher authorization remains required.
- Verify `.codex-plugin/companion.json` source revision, SHA-256 and Apache
  license, both separately packaged wheels, and offline installation in a fresh
  plugin-scoped environment. The bundled wheelhouse is Windows x64/CPython 3.12;
  other target platforms require their own verified offline dependency artifacts.
- Run `scripts/self_check.py` with the scoped Python, including old/new package
  isolation, source selection, dry-run, direct/partial/resume and free reports.
  Mock completion is not live Codex/Claude host, payment or successful upstream
  search acceptance. The authoritative Claude plugin entry remains unconfirmed.
- Deploy and verify the backend and web candidate together; no database migration is required.
- Confirm production website origin, actual privacy/terms URLs, publisher identity and support contact.
- Exercise email/Google/GitHub registration, confirmation, denial, expiry, repeated polling, interrupted credential delivery and revocation in a test environment.
- Exercise zero credits, checkout cancellation, delayed webhook, successful payment and wrong-account links with payment sandbox credentials.
- Verify actual requests and deliverables for representative bundled skills. Bundling all 140 does not establish live provider availability.
- Review the ZIP and wheel source, dependencies and proprietary license. Install the ZIP on a fresh machine and verify OS-keyring behavior. Capture screenshots with test accounts.
- Submit through https://platform.openai.com/plugins using an authorized publisher. Publication is a separate authorized action.

Positive prompts: Amazon headphone search to CSV; competitor ASIN keywords; water-bottle market research; supported marketplace product detail; Nexscope connection and balance.

Negative prompts: fix a React component; write a birthday poem; arbitrary website browser automation.

Acceptance: correct routing, no secret in conversation/logs, no false success after business errors, resumable connection, verified credit balance, complete files, no unrequested advertising mutations.
