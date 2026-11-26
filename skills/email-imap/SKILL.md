---
name: email-imap
description: Safely inspect mail and save drafts through configured IMAP/SMTP accounts.
---

# email-imap

Configure named accounts in `~/.config/email-imap/config.toml` and store app passwords in environment variables. Choose an account explicitly when more than one is configured.

Read operations are non-destructive: folders are selected read-only and messages are fetched with `BODY.PEEK`. There are no delete, move, or flag tools. Downloads write only below the configured download directory. This plugin cannot send mail. To write an email, use `email_save_draft` (CLI: `email-imap draft`), which appends the message to the account's Drafts folder (auto-detected via the `\Drafts` flag, or set `drafts_folder` on the account) and returns `sent: false`. Tell the user the draft is saved so they can review and send it from their mail client. Replies can set `reply_to_uid` for threading; attachments must live under the download dir or `attachment_roots`.

Search returns at most 50 messages per page, newest first. If the result contains `next_before_uid`, pass it as `before_uid` to fetch the next page. Use `email_unread` (CLI: `unread`) to list all unread INBOX messages at once; it returns the unread count and skips fetching when it is zero.

Supported presets: Gmail, iCloud, and Fastmail. Custom IMAP/SMTP hosts and ports may be supplied under an account's `server` table. See the repository README for the complete configuration and CLI reference.

