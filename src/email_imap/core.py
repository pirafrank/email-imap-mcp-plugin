from __future__ import annotations
import email as email_lib
import imaplib, mimetypes, re, smtplib, ssl, time
from email.header import decode_header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Any, Callable
from .config import Account, EmailConfig, Servers, resolve_servers

BODY_LIMIT, MAX_RESULTS, MAX_FOLDERS = 20_000, 25, 50

def decode_mime_header(raw: Any) -> str:
    if not raw: return ""
    out = []
    for part, charset in decode_header(str(raw)):
        if isinstance(part, bytes):
            try: out.append(part.decode(charset or "utf-8", errors="replace"))
            except LookupError: out.append(part.decode("utf-8", errors="replace"))
        else: out.append(part)
    return "".join(out)

def _decode(part):
    payload = part.get_payload(decode=True) or b""
    try: return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError: return payload.decode("utf-8", errors="replace")

def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
    html = re.sub(r"<(br|/p|/div|/tr)\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    for old, new in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")): html = html.replace(old, new)
    return re.sub(r"\n{3,}", "\n\n", html).strip()

def extract_text_body(msg) -> str:
    plain = html = ""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if "attachment" in str(part.get("Content-Disposition", "")).lower(): continue
        if part.get_content_type() == "text/plain" and not plain: plain = _decode(part)
        elif part.get_content_type() == "text/html" and not html: html = _decode(part)
    result = plain or _strip_html(html)
    return result if len(result) <= BODY_LIMIT else result[:BODY_LIMIT] + "\n…[truncated]"

def list_attachment_parts(msg):
    result = []
    if not msg.is_multipart(): return result
    for part in msg.walk():
        disposition, filename = str(part.get("Content-Disposition", "")).lower(), part.get_filename()
        if filename and ("attachment" in disposition or "inline" in disposition): result.append((decode_mime_header(filename), part))
    return result

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
def _imap_date(value: str):
    m = _DATE_RE.fullmatch(value.strip()) if value else None
    if not m: return None
    year, month, day = map(int, m.groups())
    if not 1 <= month <= 12: return None
    import calendar
    if not 1 <= day <= calendar.monthrange(year, month)[1]: return None
    return f"{day:02d}-{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month-1]}-{year}"

def _quote(value: str) -> str: return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
def build_search_criteria(*, from_address="", to_address="", subject="", text="", since="", before="", unread_only=False):
    parts = []
    for key, value in (("FROM", from_address), ("TO", to_address), ("SUBJECT", subject), ("TEXT", text)):
        if str(value).strip(): parts.append(f"{key} {_quote(str(value).strip())}")
    for key, value in (("SINCE", since), ("BEFORE", before)):
        if str(value).strip():
            date = _imap_date(str(value))
            if not date: return None, f"invalid {key.lower()} date {value!r}; use YYYY-MM-DD"
            parts.append(f"{key} {date}")
    if unread_only: parts.append("UNSEEN")
    criteria = " ".join(parts) or "ALL"
    return (criteria.encode("ascii") if criteria.isascii() else b"CHARSET UTF-8 " + criteria.encode("utf-8")), ""

def _parse_list_line(line: bytes):
    match = re.match(rb'\((?P<flags>[^)]*)\)\s+"[^"]*"\s+(?P<name>.+)$', line)
    if not match or rb"\Noselect" in match.group("flags"): return None
    name = match.group("name").strip()
    if name.startswith(b'"') and name.endswith(b'"'): name = name[1:-1].replace(b'\\"', b'"')
    return name.decode("utf-8", errors="replace")

def _safe_filename(name):
    name = Path(str(name).replace("\\", "/")).name
    return re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip(". ") or "attachment"

class EmailClient:
    def __init__(self, config: EmailConfig, *, imap_factory: Callable | None = None, smtp_factory: Callable | None = None):
        self.config = config
        self.imap_factory = imap_factory or (lambda host, port: imaplib.IMAP4_SSL(host, port, timeout=30))
        self.smtp_factory = smtp_factory or self._smtp_factory
    @staticmethod
    def _smtp_factory(host, port):
        if port == 465: return smtplib.SMTP_SSL(host, port, timeout=30, context=ssl.create_default_context())
        smtp = smtplib.SMTP(host, port, timeout=30); smtp.starttls(context=ssl.create_default_context()); return smtp
    def _imap(self, account: str | None):
        acct = self.config.account(account); imap = self.imap_factory(acct.servers.imap_host, acct.servers.imap_port); imap.login(acct.address, acct.app_password); return imap, acct
    @staticmethod
    def _close(imap):
        try: imap.logout()
        except Exception: pass
    @staticmethod
    def _select(imap, folder):
        status, _ = imap.select(_quote(folder), readonly=True)
        return None if status == "OK" else f"cannot open folder {folder!r}"
    def check(self, account=None):
        imap, acct = self._imap(account)
        try:
            error = self._select(imap, "INBOX")
            if error: raise RuntimeError(error)
            smtp = self.smtp_factory(acct.servers.smtp_host, acct.servers.smtp_port)
            try: smtp.login(acct.address, acct.app_password)
            finally:
                try: smtp.quit()
                except Exception: pass
            status, data = imap.uid("SEARCH", "UNSEEN")
            if status != "OK": raise RuntimeError("could not count unread messages in INBOX")
            unread = len(data[0].split()) if data and data[0] else 0
            return {"ok": True, "account": acct.name, "address": acct.address, "unread_inbox": unread}
        finally: self._close(imap)
    def folders(self, account=None):
        imap, _ = self._imap(account)
        try:
            status, lines = imap.list()
            if status != "OK": raise RuntimeError("could not list folders")
            folders = []
            for line in lines[:MAX_FOLDERS]:
                name = _parse_list_line(line) if isinstance(line, bytes) else None
                if name: folders.append({"name": name})
            return {"ok": True, "folders": folders}
        finally: self._close(imap)
    def _fetch(self, imap, uid):
        status, data = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
        return email_lib.message_from_bytes(data[0][1]) if status == "OK" and data and isinstance(data[0], tuple) else None
    def search(self, account=None, folder="INBOX", max_results=10, **filters):
        criteria, error = build_search_criteria(**filters)
        if criteria is None: return {"error": error}
        imap, _ = self._imap(account)
        try:
            if (error := self._select(imap, folder)): return {"error": error}
            status, data = imap.uid("SEARCH", criteria)
            if status != "OK": return {"error": "search failed"}
            uids = (data[0] or b"").split(); limit = max(1, min(int(max_results or 10), MAX_RESULTS)); messages = []
            for uid in reversed(uids[-limit:]):
                status, fetched = imap.uid("FETCH", uid.decode(), "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)] FLAGS BODYSTRUCTURE)")
                if status != "OK": continue
                raw = b""; meta = b""
                for item in fetched:
                    if isinstance(item, tuple): meta += item[0]; raw += item[1]
                    elif isinstance(item, bytes): meta += item
                msg = email_lib.message_from_bytes(raw)
                messages.append({"uid": uid.decode(), "date": decode_mime_header(msg.get("Date")), "from": decode_mime_header(msg.get("From")), "to": decode_mime_header(msg.get("To")), "subject": decode_mime_header(msg.get("Subject")), "unread": b"\\Seen" not in meta, "has_attachments": b"ATTACHMENT" in meta.upper()})
            return {"ok": True, "folder": folder, "total_matches": len(uids), "messages": messages}
        finally: self._close(imap)
    def read(self, uid, account=None, folder="INBOX"):
        imap, _ = self._imap(account)
        try:
            if (error := self._select(imap, folder)): return {"error": error}
            msg = self._fetch(imap, uid)
            if msg is None: return {"error": f"message {uid} not found in {folder}"}
            return {"ok": True, "uid": str(uid), "folder": folder, "from": decode_mime_header(msg.get("From")), "to": decode_mime_header(msg.get("To")), "cc": decode_mime_header(msg.get("Cc")), "date": decode_mime_header(msg.get("Date")), "subject": decode_mime_header(msg.get("Subject")), "body": extract_text_body(msg), "attachments": [{"filename": n, "content_type": p.get_content_type(), "size": len(p.get_payload(decode=True) or b"")} for n,p in list_attachment_parts(msg)]}
        finally: self._close(imap)
    def download(self, uid, filename, account=None, folder="INBOX"):
        imap, _ = self._imap(account)
        try:
            if (error := self._select(imap, folder)): return {"error": error}
            msg = self._fetch(imap, uid)
            if msg is None: return {"error": f"message {uid} not found in {folder}"}
            matches = [(n,p) for n,p in list_attachment_parts(msg) if n == filename]
            if not matches: return {"error": f"no attachment named {filename!r}"}
            self.config.download_dir.mkdir(parents=True, exist_ok=True); target = self.config.download_dir / _safe_filename(filename); stem, suffix = target.stem, target.suffix; counter = 1
            while target.exists(): target = self.config.download_dir / f"{stem}-{counter}{suffix}"; counter += 1
            payload = matches[0][1].get_payload(decode=True) or b""; target.write_bytes(payload)
            return {"ok": True, "path": str(target), "size": len(payload)}
        finally: self._close(imap)
    def _drafts_folder(self, imap, acct):
        if acct.drafts_folder: return acct.drafts_folder
        status, lines = imap.list(); names = []
        if status == "OK":
            for line in lines or []:
                if not isinstance(line, bytes): continue
                name = _parse_list_line(line)
                if not name: continue
                if rb"\Drafts" in line.split(b")",1)[0]: return name
                names.append(name)
        for candidate in ("Drafts", "[Gmail]/Drafts", "INBOX.Drafts", "Draft"):
            if candidate in names: return candidate
        return None
    def save_draft(self, to, subject, body, account=None, cc="", bcc="", reply_to_uid="", reply_to_folder="INBOX", attachments=None):
        """Build a message and store it in the Drafts folder. Never sends."""
        acct = self.config.account(account); msg = EmailMessage(); msg["From"] = formataddr((acct.display_name, acct.address)) if acct.display_name else acct.address
        if to: msg["To"] = to
        if cc: msg["Cc"] = cc
        if bcc: msg["Bcc"] = bcc
        msg["Date"] = formatdate(localtime=True); msg["Message-ID"] = make_msgid(domain=acct.address.rsplit("@",1)[-1])
        imap, _ = self._imap(account)
        try:
            if reply_to_uid:
                if (error := self._select(imap, reply_to_folder)): return {"error": error}
                status, data = imap.uid("FETCH", str(reply_to_uid), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES SUBJECT)])")
                if status != "OK" or not data or not isinstance(data[0], tuple): return {"error": f"reply target {reply_to_uid} not found in {reply_to_folder}"}
                original = email_lib.message_from_bytes(data[0][1]); message_id = str(original.get("Message-ID", "")).strip()
                if message_id: msg["In-Reply-To"] = message_id; msg["References"] = f"{str(original.get('References','')).strip()} {message_id}".strip()
                if not subject: subject = decode_mime_header(original.get("Subject")); subject = subject if subject.lower().startswith("re:") else "Re: " + subject
            msg["Subject"] = subject; msg.set_content(body)
            allowed = (self.config.download_dir, *self.config.attachment_roots)
            for raw in attachments or []:
                path = Path(raw).expanduser().resolve()
                if not any(path == root or root in path.parents for root in allowed): return {"error": f"attachment {raw} is outside configured attachment roots"}
                if not path.is_file(): return {"error": f"attachment not found: {raw}"}
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"; main, sub = ctype.split("/",1); msg.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
            folder = self._drafts_folder(imap, acct)
            if not folder: return {"error": "could not find a Drafts folder; set drafts_folder on the account"}
            status, _ = imap.append(_quote(folder), "(\\Draft)", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
            if status != "OK": return {"error": f"could not save draft to {folder!r}"}
            return {"ok": True, "saved": True, "sent": False, "folder": folder, "message_id": msg["Message-ID"], "subject": subject}
        finally: self._close(imap)
