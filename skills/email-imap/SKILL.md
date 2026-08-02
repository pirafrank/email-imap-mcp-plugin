---
name: email-imap
description: Safely inspect and send mail through configured IMAP/SMTP accounts.
---

# email-imap

Configure named accounts in `~/.config/email-imap/config.toml` and store app passwords in environment variables. Choose an account explicitly when more than one is configured.

Read operations are non-destructive: folders are selected read-only and messages are fetched with `BODY.PEEK`. There are no delete, move, or flag tools. Downloads write only below the configured download directory. Sending is an external side effect and requires approval; the CLI additionally requires `--yes`.

Supported presets: Gmail, iCloud, and Fastmail. Custom IMAP/SMTP hosts and ports may be supplied under an account's `server` table. See the repository README for the complete configuration and CLI reference.

