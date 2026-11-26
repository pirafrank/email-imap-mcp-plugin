# email-imap-mcp-plugin

Standalone IMAP/SMTP access for Codex. Mailbox reads use read-only folder selection and `BODY.PEEK`; the plugin does not delete, move, or flag messages. Saving drafts (to the account's Drafts folder) and attachment downloads are the only write-capable operations. The plugin cannot send mail: there is no send tool or command.

## Install

1. Install the executables (`email-imap` and `email-imap-mcp`) onto your PATH:

   ```sh
   uv tool install --reinstall .     # or: pipx install --force .
   which email-imap-mcp              # should print a path
   ```

   Re-run with `--reinstall` / `--force` after pulling changes, otherwise the old build is kept.

2. Create the config file (see [Configuration](#configuration)), then verify:

   ```sh
   email-imap check --account NAME   # reports login status and unread_inbox
   ```

3. Register the MCP server with your client. All clients just launch `email-imap-mcp` over stdio; add `--config /path/to/config.toml` after it for a non-default config. Restart the client (or start a new session) afterwards, since MCP servers load at session start.

   **Claude Code** — from your project directory, either use the bundled `.mcp.json` (approve `email-imap` when prompted) or run:

   ```sh
   claude mcp add email-imap --scope user -- email-imap-mcp
   ```

   Check with `/mcp`.

   **Codex** — register the server directly:

   ```sh
   codex mcp add email-imap -- email-imap-mcp
   codex mcp list
   ```

   This writes to `~/.codex/config.toml`; the equivalent manual entry is:

   ```toml
   [mcp_servers.email-imap]
   command = "email-imap-mcp"
   # args = ["--config", "/path/to/config.toml"]
   ```

   The repo also contains a Codex plugin manifest in `.codex-plugin/` (with `.mcp.json` and the `skills/email-imap` skill); the direct registration above does not depend on it.

   **pi** — add the server globally (`~/.pi/agent/mcp.json`) or, with `-l`, for the current project only (`.pi/mcp.json`, trusted projects only):

   ```sh
   pi mcp add email-imap -- email-imap-mcp
   pi mcp list            # shows state, tools and errors
   ```

   Optional flags: `--description "Read mail via IMAP"` (shown in the system prompt) and `--exposure direct` (default is `codemode`; `direct` exposes each tool individually).

   **Orca (orca.dev)** — Orca runs agents (Claude Code, Codex, pi, ...) in its terminals and does not have a separate MCP registry; its `orca plugin` system is for Orca UI plugins, not MCP servers. Register `email-imap-mcp` with the agent you run inside Orca using the matching section above, then start a new agent session in an Orca workspace.

If the client reports `Executable not found in $PATH: email-imap-mcp`, the install in step 1 is missing or `~/.local/bin` is not on the PATH seen by the client.

MCP tools: `email_list_folders`, `email_search`, `email_unread`, `email_read`, `email_download_attachment`, `email_save_draft`.

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
# drafts_folder = "Drafts"   # optional; auto-detected via the \Drafts IMAP flag

[accounts.personal.server]
# Optional for Gmail, iCloud, and Fastmail presets.
# imap_host = "imap.example.com"
# imap_port = 993
# smtp_host = "smtp.example.com"
# smtp_port = 587
```

Supported presets are Gmail, iCloud, and Fastmail. Custom providers (e.g. Zoho: `imap.zoho.eu`/`smtp.zoho.eu`, port 465; use `.com`, `.in`, etc. for your data center) must configure both hosts. Password references are resolved from the environment and are never shown by `accounts` or status output.

## CLI

`check`, `folders`, `search`, `unread`, `read UID`, `download UID FILENAME`, `draft`, and `accounts` are available. Mailbox commands accept `--account NAME`, and all commands support `--json` for stable machine-readable output. Search supports `--from`, `--to`, `--subject`, `--text`, `--since`, `--before`, `--unread`, `--max-results` (default and maximum 50), and `--before-uid`. Search is newest-first and paginated: when more results remain, the response has `next_before_uid`; pass it as `--before-uid` (MCP: `before_uid`) for the next page. `unread` lists every unread INBOX message; it counts first and skips fetching when there are none.

Example:

```sh
email-imap search --account personal --unread --json
email-imap draft --to friend@example.com --subject Hello --body 'Hi!'
```

Attachments to include in a draft must be inside `download_dir` or a configured `attachment_roots` entry. Downloaded names are sanitized and collisions receive a numeric suffix.

## Troubleshooting

Use an app password, not the normal account password. For custom providers verify IMAP/SMTP ports and whether SMTP uses STARTTLS (587) or implicit TLS (465). Configuration errors are reported on stderr with exit code 1.

## Credits

email-imap has been developed as part of [OpenWorker](https://github.com/andrewyng/openworker). It has been extracted and refactor to work as a standalone plugin for Codex. 

## License

This project is licensed under the MIT License.
