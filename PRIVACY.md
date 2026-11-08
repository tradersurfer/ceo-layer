# Privacy — deliberately excluded from the public CEO Pack

This build was made for a public Hermes plugin catalog submission. The following were NOT copied into `ceo-pack/`, even though they exist on the author's local machine or in private Drive folders:

- Any private business information, data, or client data
- Business prices, offers, or service lists from any private site source
- Business locations, segments, or client lists
- Personal names, personal portraits, or personal animations from any local pack
- Any `.env` file, credential, API key, token, or login
- Any log, screenshot, or file from a private Hermes profile or local cache
- Any connected-account data (books, Drive, email, or similar)
- The full original web app (app, CLI, desktop, website, tests) — only generic engine concepts, department prompts, and docs were adapted, in Python, for Hermes

What IS included, and why it is safe to publish:

- Generic CEO/C-suite role sheets with placeholder owners
- Department prompts that already use `{{AGENT_NAME}}`, `{{BUSINESS_CONTEXT}}`, and `{{PRINCIPAL_NAME}}` placeholders
- Sanitized docs, with company names replaced with `[Your Company]`
- New Python tools with no network access, no file writes, and no credential reads
- A config schema that asks the installer for their own business name and owner name — nothing is pre-filled

Before pushing this to a public repo or catalog PR, run the local privacy check kept outside this folder and review the diff by hand. If a private value ever appears, remove it before committing — a catalog pin is a full commit SHA, and reviewers read exactly that commit.

## Added in 0.3.0

- Tool arguments are scanned for credential-like keys and values. Detected values are never echoed in errors or logs, only their path.
- The test suite and demo use only fictional inputs and obviously fake strings (for example `sb_secret_FAKE123`).
- Still true: no network, no file writes, no credential reads.
