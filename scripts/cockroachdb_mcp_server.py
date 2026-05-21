#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - import guard for local setup
    print(
        "Missing dependency 'mcp'. Run `python3 -m pip install -r requirements.txt`.",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError as exc:  # pragma: no cover - import guard for local setup
    print(
        "Missing dependency 'psycopg'. Run `python3 -m pip install -r requirements.txt`.",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


mcp = FastMCP("CockroachDB", json_response=True)

READ_ONLY_START_KEYWORDS = {
    "SELECT",
    "SHOW",
    "EXPLAIN",
    "VALUES",
    "WITH",
    "DESC",
    "DESCRIBE",
}

BLOCKED_SQL_KEYWORDS = {
    "ALTER",
    "BACKUP",
    "CANCEL",
    "COMMENT",
    "COPY",
    "CREATE",
    "DELETE",
    "DROP",
    "EXPORT",
    "GRANT",
    "IMPORT",
    "INSERT",
    "PAUSE",
    "RELOCATE",
    "RENAME",
    "RESET",
    "RESTORE",
    "REVOKE",
    "SCRUB",
    "SET",
    "SPLIT",
    "TRUNCATE",
    "UPSERT",
    "UPDATE",
}

SYSTEM_SCHEMAS = ("crdb_internal", "information_schema", "pg_catalog", "pg_extension")
DEFAULT_ROW_LIMIT = 200
MAX_ROW_LIMIT = 1000


def _connection_url() -> str:
    url = os.getenv("COCKROACHDB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Set COCKROACHDB_URL (preferred) or DATABASE_URL before starting the plugin."
        )
    return url


def _connect() -> psycopg.Connection[Any]:
    timeout = int(os.getenv("COCKROACHDB_CONNECT_TIMEOUT", "10"))
    return psycopg.connect(_connection_url(), autocommit=True, connect_timeout=timeout)


def _default_schema() -> str:
    return os.getenv("COCKROACHDB_DEFAULT_SCHEMA", "public")


def _default_row_limit() -> int:
    raw_value = os.getenv("COCKROACHDB_ROW_LIMIT", str(DEFAULT_ROW_LIMIT))
    try:
        limit = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("COCKROACHDB_ROW_LIMIT must be an integer.") from exc
    return max(1, min(limit, MAX_ROW_LIMIT))


def _strip_leading_comments(query: str) -> str:
    remaining = query.strip()
    while True:
        if remaining.startswith("--"):
            newline = remaining.find("\n")
            if newline == -1:
                return ""
            remaining = remaining[newline + 1 :].lstrip()
            continue
        if remaining.startswith("/*"):
            end = remaining.find("*/")
            if end == -1:
                return ""
            remaining = remaining[end + 2 :].lstrip()
            continue
        return remaining


def _normalize_query(query: str) -> str:
    normalized = _strip_leading_comments(query)
    if not normalized:
        raise ValueError("Query is empty.")
    return normalized


def _ensure_read_only(query: str) -> str:
    normalized = _normalize_query(query)
    first_match = re.match(r"^[A-Za-z]+", normalized)
    if first_match is None:
        raise ValueError("Query must start with a SQL keyword.")

    first_keyword = first_match.group(0).upper()
    if first_keyword not in READ_ONLY_START_KEYWORDS:
        raise ValueError(
            f"Only read-only SQL is allowed. Received statement starting with '{first_keyword}'."
        )

    upper_query = normalized.upper()
    for keyword in BLOCKED_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_query):
            raise ValueError(
                f"Blocked SQL keyword detected: '{keyword}'. This plugin only allows read-only access."
            )

    return normalized


def _normalize_limit(row_limit: int | None) -> int:
    if row_limit is None:
        return _default_row_limit()
    return max(1, min(row_limit, MAX_ROW_LIMIT))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, time, UUID)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: _json_safe(value) for key, value in row.items()} for row in rows]


def _fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with _connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return list(cur.fetchall())


@mcp.tool()
def connection_info() -> dict[str, Any]:
    """Return connectivity details for the current CockroachDB connection."""
    rows = _fetch_all(
        """
        SELECT
          current_database() AS database_name,
          current_schema() AS schema_name,
          current_user AS user_name,
          version() AS version
        """
    )
    return rows[0]


@mcp.tool()
def list_schemas() -> dict[str, Any]:
    """List non-system schemas in the current database."""
    rows = _fetch_all(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE catalog_name = current_database()
          AND schema_name <> ALL(%s)
        ORDER BY schema_name
        """,
        (list(SYSTEM_SCHEMAS),),
    )
    return {"schemas": _serialize_rows(rows)}


@mcp.tool()
def list_tables(schema: str | None = None) -> dict[str, Any]:
    """List tables and views in the current database, optionally filtered by schema."""
    if schema:
        rows = _fetch_all(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_catalog = current_database()
              AND table_schema = %s
            ORDER BY table_schema, table_name
            """,
            (schema,),
        )
    else:
        rows = _fetch_all(
            """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_catalog = current_database()
              AND table_schema <> ALL(%s)
            ORDER BY table_schema, table_name
            """,
            (list(SYSTEM_SCHEMAS),),
        )
    return {"tables": _serialize_rows(rows)}


@mcp.tool()
def describe_table(table_name: str, schema: str | None = None) -> dict[str, Any]:
    """Describe a table with columns, indexes, and its CREATE TABLE statement."""
    target_schema = schema or _default_schema()
    columns = _fetch_all(
        """
        SELECT
          ordinal_position,
          column_name,
          data_type,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_catalog = current_database()
          AND table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (target_schema, table_name),
    )

    if not columns:
        raise ValueError(f"Table '{target_schema}.{table_name}' was not found.")

    with _connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                sql.SQL("SHOW INDEXES FROM TABLE {}.{}").format(
                    sql.Identifier(target_schema),
                    sql.Identifier(table_name),
                )
            )
            indexes = list(cur.fetchall())

            cur.execute(
                sql.SQL("SHOW CREATE TABLE {}.{}").format(
                    sql.Identifier(target_schema),
                    sql.Identifier(table_name),
                )
            )
            create_statement = dict(cur.fetchone() or {})

    return {
        "schema": target_schema,
        "table": table_name,
        "columns": _serialize_rows(columns),
        "indexes": _serialize_rows(indexes),
        "create_statement": {key: _json_safe(value) for key, value in create_statement.items()},
    }


@mcp.tool()
def run_readonly_query(query: str, row_limit: int | None = None) -> dict[str, Any]:
    """Run a read-only SQL query and return a bounded set of structured rows."""
    safe_query = _ensure_read_only(query)
    limit = _normalize_limit(row_limit)

    with _connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(safe_query)
            rows = list(cur.fetchmany(limit + 1))
            columns = [column.name for column in cur.description or ()]

    truncated = len(rows) > limit
    visible_rows = rows[:limit]
    return {
        "columns": columns,
        "row_limit": limit,
        "returned_rows": len(visible_rows),
        "truncated": truncated,
        "rows": _serialize_rows(visible_rows),
    }


@mcp.tool()
def explain_query(query: str, analyze: bool = False) -> dict[str, Any]:
    """Run EXPLAIN on a read-only SQL query."""
    safe_query = _ensure_read_only(query)
    if re.match(r"^[A-Za-z]+", safe_query).group(0).upper() == "EXPLAIN":
        explain_sql = safe_query
    else:
        explain_prefix = "EXPLAIN ANALYZE " if analyze else "EXPLAIN "
        explain_sql = f"{explain_prefix}{safe_query}"
    return run_readonly_query(explain_sql, row_limit=MAX_ROW_LIMIT)


if __name__ == "__main__":
    mcp.run()
