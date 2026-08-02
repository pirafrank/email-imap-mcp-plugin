# email-imap-mcp-plugin

Standalone IMAP/SMTP access for Codex. Mailbox reads use read-only folder selection and `BODY.PEEK`; the plugin does not delete, move, or flag messages. Sending and attachment downloads are the only write-capable operations, and CLI sending requires `--yes`.

## Install

```sh
python -m pip install .
email-imap accounts
```

The Codex plugin manifest is in `.codex-plugin/`; `.mcp.json` starts the installed `email-imap-mcp` executable.

## Configuration

By default, the file is `~/.config/email-imap/config.toml` (Windows: `%APPDATA%/email-imap/config.toml`). Use `--config PATH` to override it.

```toml
[defaults]
account = "personal"
download_dir = "~/Downloads/email-imap"
attachment_roots = ["~/Documents/to-send"]

[accounts.personal]
address = "email@gmail.com"
app_password = "${EMAIL_IMAP_PERSONAL_PASSWORD}"
display_name = "Francesco"

[accounts.personal.server]
# Optional for Gmail, iCloud, and Fastmail presets.
# imap_host = "imap.example.com"
# imap_port = 993
# smtp_host = "smtp.example.com"
# smtp_port = 587
```

Supported presets are Gmail, iCloud, and Fastmail. Custom providers must configure both hosts. Password references are resolved from the environment and are never shown by `accounts` or status output.

## CLI

`check`, `folders`, `search`, `read UID`, `download UID FILENAME`, `send`, and `accounts` are available. Mailbox commands accept `--account NAME`, and all commands support `--json` for stable machine-readable output. Search supports `--from`, `--to`, `--subject`, `--text`, `--since`, `--before`, `--unread`, and `--max-results`.

Example:

```sh
email-imap search --account personal --unread --json
email-imap send --to friend@example.com --subject Hello --body 'Hi!' --yes
```

Attachments to send must be inside `download_dir` or a configured `attachment_roots` entry. Downloaded names are sanitized and collisions receive a numeric suffix.

## Troubleshooting

Use an app password, not the normal account password. For custom providers verify IMAP/SMTP ports and whether SMTP uses STARTTLS (587) or implicit TLS (465). Configuration errors are reported on stderr with exit code 1; an unconfirmed send exits 2.

## Credits

email-imap has been developed as part of [OpenWorker](https://github.com/andrewyng/openworker). It has been extracted and refactor to work as a standalone plugin for Codex. 

## License

This project is licensed under the MIT License.
