from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text

PROBE_SQL = text(
    "select current_database(), current_schema(), inet_server_addr(), inet_server_port()"
)


def mask_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url

    masked_netloc = parts.netloc.replace(parts.password, "***", 1)
    return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))
