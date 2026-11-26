from __future__ import annotations
from .config import load_config
from .core import EmailClient

def create_server(config_path=None):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("email-imap")
    def client(): return EmailClient(load_config(config_path))
    @mcp.tool(description="Read-only: list mailbox folders and message counts.")
    def email_list_folders(account: str = "") -> dict: return client().folders(account or None)
    @mcp.tool(description="Read-only: search a mailbox, newest first; never marks messages read. Max 50 per page; if the result has next_before_uid, pass it as before_uid to get the next page.")
    def email_search(account: str = "", folder: str = "INBOX", from_address: str = "", to_address: str = "", subject: str = "", text: str = "", since: str = "", before: str = "", unread_only: bool = False, max_results: int = 50, before_uid: str = "") -> dict:
        return client().search(account or None, folder, max_results, before_uid, from_address=from_address, to_address=to_address, subject=subject, text=text, since=since, before=before, unread_only=unread_only)
    @mcp.tool(description="Read-only: list ALL unread INBOX messages (headers only, newest first); counts first and skips fetching if none. Never marks messages read.")
    def email_unread(account: str = "") -> dict: return client().unread(account or None)
    @mcp.tool(description="Read-only: read one message by UID with decoded body and attachment metadata.")
    def email_read(uid: str, account: str = "", folder: str = "INBOX") -> dict: return client().read(uid, account or None, folder)
    @mcp.tool(description="Risk: downloads an attachment into the configured download directory; requires approval.")
    def email_download_attachment(uid: str, filename: str, account: str = "", folder: str = "INBOX") -> dict: return client().download(uid, filename, account or None, folder)
    @mcp.tool(description="Write: saves a plain-text message to the account's Drafts folder for the user to review. Does NOT send; there is no send tool.")
    def email_save_draft(to: str, subject: str, body: str, account: str = "", cc: str = "", bcc: str = "", reply_to_uid: str = "", folder: str = "INBOX", attachments: list[str] | None = None) -> dict: return client().save_draft(to, subject, body, account or None, cc, bcc, reply_to_uid, folder, attachments)
    return mcp

def main():
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--config"); args = p.parse_args()
    create_server(args.config).run(transport="stdio")

