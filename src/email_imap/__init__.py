"""Standalone, read-safe IMAP/SMTP tools for Codex."""

from .config import Account, ConfigError, EmailConfig, load_config, resolve_servers
from .core import EmailClient

__all__ = ["Account", "ConfigError", "EmailClient", "EmailConfig", "load_config", "resolve_servers"]

