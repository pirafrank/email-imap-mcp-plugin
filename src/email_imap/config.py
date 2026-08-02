from __future__ import annotations

import os
import re
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from tomli import TOMLDecodeError  # type: ignore
except ImportError:
    TOMLDecodeError = tomllib.TOMLDecodeError

class ConfigError(ValueError):
    pass

@dataclass(frozen=True)
class Servers:
    imap_host: str
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587

EmailServers = Servers

_PRESETS = {
    "gmail.com": Servers("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "googlemail.com": Servers("imap.gmail.com", 993, "smtp.gmail.com", 587),
    "icloud.com": Servers("imap.mail.me.com", 993, "smtp.mail.me.com", 587),
    "me.com": Servers("imap.mail.me.com", 993, "smtp.mail.me.com", 587),
    "mac.com": Servers("imap.mail.me.com", 993, "smtp.mail.me.com", 587),
    "fastmail.com": Servers("imap.fastmail.com", 993, "smtp.fastmail.com", 465),
}

def resolve_servers(profile: dict[str, Any]) -> tuple[Servers | None, str]:
    address = str(profile.get("address", "")).strip()
    domain = address.rsplit("@", 1)[-1].lower() if "@" in address else ""
    preset = _PRESETS.get(domain)
    def value(name: str, default: int) -> int:
        raw = profile.get(name, default)
        try: result = int(raw)
        except (TypeError, ValueError): raise ConfigError(f"{name} must be an integer")
        if not 1 <= result <= 65535: raise ConfigError(f"{name} must be between 1 and 65535")
        return result
    imap_host = str(profile.get("imap_host") or (preset.imap_host if preset else "")).strip()
    smtp_host = str(profile.get("smtp_host") or (preset.smtp_host if preset else "")).strip()
    if not imap_host or not smtp_host:
        return None, f"no server preset for '{domain or address}'; configure IMAP and SMTP hosts"
    return Servers(imap_host, value("imap_port", preset.imap_port if preset else 993),
                   smtp_host, value("smtp_port", preset.smtp_port if preset else 587)), ""

@dataclass(frozen=True)
class Account:
    name: str
    address: str
    app_password: str
    display_name: str = ""
    servers: Servers = field(default_factory=lambda: Servers("", 993, "", 587))

@dataclass(frozen=True)
class EmailConfig:
    accounts: dict[str, Account]
    default_account: str
    download_dir: Path
    attachment_roots: tuple[Path, ...] = ()
    source_path: Path | None = None

    def account(self, name: str | None = None) -> Account:
        selected = name or self.default_account
        try: return self.accounts[selected]
        except KeyError: raise ConfigError(f"unknown account {selected!r}; use accounts to list configured accounts")

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
def _expand(value: Any) -> Any:
    if isinstance(value, dict): return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list): return [_expand(v) for v in value]
    if not isinstance(value, str): return value
    missing = []
    def sub(match):
        key = match.group(1)
        if key not in os.environ: missing.append(key); return match.group(0)
        return os.environ[key]
    result = _ENV.sub(sub, value)
    if missing: raise ConfigError("unresolved environment variable reference(s): " + ", ".join(sorted(set(missing))))
    return result

def default_config_path() -> Path:
    if sys.platform == "win32": base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else: base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "email-imap" / "config.toml"

def load_config(path: str | Path | None = None) -> EmailConfig:
    source = Path(path).expanduser() if path else default_config_path()
    if not source.is_file(): raise ConfigError(f"configuration file not found: {source}")
    try:
        with source.open("rb") as handle: raw = tomllib.load(handle)
    except (OSError, TOMLDecodeError) as exc: raise ConfigError(f"invalid configuration: {exc}") from exc
    raw = _expand(raw)
    defaults = raw.get("defaults", {})
    entries = raw.get("accounts", {})
    if not isinstance(entries, dict) or not entries: raise ConfigError("at least one account is required")
    accounts = {}
    for name, data in entries.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name): raise ConfigError(f"invalid account name: {name!r}")
        if not isinstance(data, dict): raise ConfigError(f"account {name!r} must be a table")
        address, password = str(data.get("address", "")).strip(), data.get("app_password")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+", address): raise ConfigError(f"account {name!r} has an invalid address")
        if not isinstance(password, str) or not password: raise ConfigError(f"account {name!r} is missing app_password")
        merged = dict(data); merged.update(data.get("server", {}))
        try: servers, error = resolve_servers(merged)
        except ConfigError as exc: raise ConfigError(f"account {name!r}: {exc}") from exc
        if servers is None: raise ConfigError(f"account {name!r}: {error}")
        accounts[name] = Account(name, address, password, str(data.get("display_name", "")), servers)
    selected = str(defaults.get("account") or next(iter(accounts)))
    if selected not in accounts: raise ConfigError(f"default account {selected!r} is not configured")
    download = Path(str(defaults.get("download_dir", "~/Downloads/email-imap"))).expanduser().resolve()
    roots = tuple(Path(str(p)).expanduser().resolve() for p in defaults.get("attachment_roots", []))
    return EmailConfig(accounts, selected, download, roots, source)
