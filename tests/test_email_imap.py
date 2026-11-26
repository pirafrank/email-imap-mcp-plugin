import os
from pathlib import Path
import pytest

from email_imap.config import ConfigError, load_config, resolve_servers
from email_imap.core import EmailClient, build_search_criteria, extract_text_body
from email.message import EmailMessage

def test_presets_custom_and_dates():
    servers, error = resolve_servers({"address": "x@fastmail.com"})
    assert not error and servers.smtp_port == 465
    servers, error = resolve_servers({"address": "x@example.test", "imap_host": "i", "smtp_host": "s", "imap_port": 1993})
    assert not error and servers.imap_port == 1993
    criteria, error = build_search_criteria(text="café", since="2026-02-03")
    assert not error and criteria.startswith(b"CHARSET UTF-8")
    assert build_search_criteria(since="2026-02-31")[0] is None

def test_config_env_and_no_secret_leak(tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_PASSWORD", "secret-value")
    path = tmp_path / "config.toml"
    path.write_text('''[defaults]\naccount = "work"\ndownload_dir = "~/Downloads/mail"\n[accounts.work]\naddress = "me@example.test"\napp_password = "${EMAIL_TEST_PASSWORD}"\n[accounts.work.server]\nimap_host = "imap.example.test"\nsmtp_host = "smtp.example.test"\n''')
    config = load_config(path)
    assert config.account().app_password == "secret-value"
    assert "secret-value" not in repr({"address": config.account().address})
    monkeypatch.delenv("EMAIL_TEST_PASSWORD")
    with pytest.raises(ConfigError, match="unresolved"):
        load_config(path)

class FakeIMAP:
    def __init__(self, *_): self.calls = []
    def login(self, *_): return ("OK", [])
    def select(self, folder, readonly=False): self.calls.append(("select", folder, readonly)); return ("OK", [b"1"])
    def uid(self, command, uid, payload=None):
        self.calls.append((command, uid, payload))
        if command == "SEARCH": return ("OK", [b"1 2"])
        msg = EmailMessage(); msg["From"] = "sender@example.test"; msg["Subject"] = "Hello"; msg.set_content("body")
        return ("OK", [(b"FLAGS (\\Seen) BODYSTRUCTURE", msg.as_bytes())])
    def logout(self): pass

def test_reads_are_readonly_and_peek(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('''[accounts.a]\naddress = "me@example.test"\napp_password = "pw"\n[accounts.a.server]\nimap_host = "imap.example.test"\nsmtp_host = "smtp.example.test"\n''')
    made = []
    def factory(*args):
        value = FakeIMAP(*args); made.append(value); return value
    client = EmailClient(load_config(path), imap_factory=factory)
    assert client.read("1", "a")["body"] == "body\n"
    assert made[0].calls[0] == ("select", '"INBOX"', True)
    assert made[0].calls[1][2] == "(BODY.PEEK[])"


def test_check_reports_inbox_unread_count(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('''[accounts.a]\naddress = "me@example.test"\napp_password = "pw"\n[accounts.a.server]\nimap_host = "i"\nsmtp_host = "s"\n''')
    class SMTP:
        def login(self, *_): pass
        def quit(self): pass
    made = []
    def factory(*args):
        made.append(FakeIMAP(*args)); return made[-1]
    result = EmailClient(load_config(path), imap_factory=factory, smtp_factory=lambda *_: SMTP()).check("a")
    assert result["unread_inbox"] == 2
    assert made[0].calls[0] == ("select", '"INBOX"', True)
    assert ("SEARCH", "UNSEEN", None) in made[0].calls
