"""Compatibility-friendly public email helpers."""
from .config import EmailServers, Servers, resolve_servers
from .core import (EmailClient, build_search_criteria, decode_mime_header,
                   extract_text_body, list_attachment_parts)

__all__ = ["EmailClient", "EmailServers", "Servers", "build_search_criteria", "decode_mime_header", "extract_text_body", "list_attachment_parts", "resolve_servers"]

