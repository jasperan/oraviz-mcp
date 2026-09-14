#!/usr/bin/env python
"""
Oracle Viz MCP Server
Minimal, visualization-first MCP server for Oracle AI Database (26ai Free included).
Query data, profile tables, and render charts -- nothing else.
"""

from __future__ import annotations

import array
import decimal
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import dotenv
import oracledb
import structlog
from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from oraviz_mcp.charts import CHART_TYPES, ChartError, render_chart

# ---------------------------------------------------------------------------
# Logging (stderr only: stdout belongs to the stdio MCP transport)
# ---------------------------------------------------------------------------


def _log_level() -> int:
    try:
        return int(os.environ.get("LOG_LEVEL", "20"))
    except ValueError:
        return 20


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        (
            structlog.dev.ConsoleRenderer()
            if os.getenv("LOG_FORMAT", "json") != "json"
            else structlog.processors.JSONRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level()),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

dotenv.load_dotenv()
mcp = FastMCP("Oracle Viz MCP")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TransportType(str, Enum):
    """Supported MCP server transport types."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"

    @classmethod
    def values(cls) -> list[str]:
        """Get all valid transport values."""
        return [transport.value for transport in cls]


@dataclass
class MCPServerConfig:
    """MCP transport configuration."""

    mcp_server_transport: str = None
    mcp_bind_host: str = None
    mcp_bind_port: int = None

    def __post_init__(self):
        """Validate MCP configuration."""
        if not self.mcp_server_transport:
            raise ValueError("MCP SERVER TRANSPORT is required")
        if not self.mcp_bind_host:
            raise ValueError("MCP BIND HOST is required")
        if not self.mcp_bind_port:
            raise ValueError("MCP BIND PORT is required")


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable, falling back with a warning."""
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid integer environment variable, using default", variable=name, default=default)
        return default


@dataclass
class OracleConfig:
    """Oracle connection and server configuration."""

    user: str
    password: str
    host: str
    port: int
    service: str
    # Optional: full EZConnect descriptor, e.g. "myhost:1521/FREEPDB1".
    dsn: Optional[str] = None
    # Optional: Oracle wallet (Autonomous Database / mTLS).
    config_dir: Optional[str] = None
    wallet_location: Optional[str] = None
    wallet_password: Optional[str] = None
    connect_timeout: int = 10
    max_rows: int = 500
    preview_rows: int = 25
    max_cell_chars: int = 500
    mcp_server_config: Optional[MCPServerConfig] = None

    def connection_dsn(self) -> str:
        """Return the DSN to hand to python-oracledb."""
        return self.dsn or f"{self.host}:{self.port}/{self.service}"

    def ensure_configured(self) -> None:
        """Raise if the server is not ready to connect."""
        if not self.user or not self.password:
            raise ValueError(
                "Oracle configuration is missing. Please set ORACLE_USER and "
                "ORACLE_PASSWORD (and ORACLE_HOST/ORACLE_PORT/ORACLE_SERVICE, "
                "or ORACLE_DSN) environment variables."
            )


config = OracleConfig(
    user=os.environ.get("ORACLE_USER", ""),
    password=os.environ.get("ORACLE_PASSWORD", ""),
    host=os.environ.get("ORACLE_HOST", "localhost"),
    port=_int_env("ORACLE_PORT", 1521),
    service=os.environ.get("ORACLE_SERVICE", "FREEPDB1"),
    dsn=os.environ.get("ORACLE_DSN") or None,
    config_dir=os.environ.get("ORACLE_CONFIG_DIR") or None,
    wallet_location=os.environ.get("ORACLE_WALLET_LOCATION") or None,
    wallet_password=os.environ.get("ORACLE_WALLET_PASSWORD") or None,
    connect_timeout=_int_env("ORACLE_CONNECT_TIMEOUT", 10),
    max_rows=_int_env("ORACLE_MCP_MAX_ROWS", 500),
    preview_rows=_int_env("ORACLE_MCP_PREVIEW_ROWS", 25),
    max_cell_chars=_int_env("ORACLE_MCP_MAX_CELL_CHARS", 500),
    mcp_server_config=MCPServerConfig(
        mcp_server_transport=os.environ.get("ORACLE_MCP_SERVER_TRANSPORT", "stdio").lower(),
        mcp_bind_host=os.environ.get("ORACLE_MCP_BIND_HOST", "127.0.0.1"),
        mcp_bind_port=_int_env("ORACLE_MCP_BIND_PORT", 8080),
    ),
)

# ---------------------------------------------------------------------------
# Oracle client
# ---------------------------------------------------------------------------


def get_oracle_connection() -> oracledb.Connection:
    """Open a python-oracledb connection (thin mode by default: no Oracle client needed)."""
    config.ensure_configured()
    connection_arguments: Dict[str, Any] = {
        "user": config.user,
        "password": config.password,
        "dsn": config.connection_dsn(),
        "tcp_connect_timeout": config.connect_timeout,
    }
    if config.config_dir:
        connection_arguments["config_dir"] = config.config_dir
    if config.wallet_location:
        connection_arguments["wallet_location"] = config.wallet_location
    if config.wallet_password:
        connection_arguments["wallet_password"] = config.wallet_password

    try:
        connection = oracledb.connect(**connection_arguments)
        connection.fetch_lobs = False  # return CLOB as str and BLOB as bytes
        logger.debug("Oracle connection established", dsn=config.connection_dsn())
        return connection
    except oracledb.Error as error:
        logger.error(
            "Failed to connect to Oracle",
            error=str(error),
            exception_type=type(error).__name__,
            dsn=config.connection_dsn(),
        )
        raise


def format_value(value: Any) -> Any:
    """Convert an Oracle value into something JSON-friendly and context-friendly."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, decimal.Decimal):
        number = float(value)
        return number if math.isfinite(number) else str(value)
    if isinstance(value, datetime):
        # Midnight timestamps are dates in practice; keep the cell short.
        return value.date().isoformat() if value.time() == time(0, 0) else value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<binary {len(value)} bytes>"
    if isinstance(value, array.array):  # dense VECTOR column
        return f"<VECTOR({len(value)})>"
    if hasattr(value, "num_elements") and hasattr(value, "values"):  # sparse VECTOR column
        return f"<VECTOR({len(value.values)})>"
    if hasattr(value, "read"):  # LOB that fetch_lobs did not convert
        data = value.read()
        return data if isinstance(data, str) else f"<binary {len(data)} bytes>"
    text = str(value)
    limit = config.max_cell_chars if config.max_cell_chars > 0 else 500
    return text if len(text) <= limit else text[:limit] + "..."


def _fetch_rows(cursor: oracledb.Cursor) -> Tuple[List[str], List[tuple]]:
    """Return (columns, rows) from a cursor's current fetch window."""
    columns = [description[0] for description in (cursor.description or [])]
    if not columns:
        return [], []
    return columns, cursor.fetchall()


# ---------------------------------------------------------------------------
# Context-engineered rendering
#
# Agents pay for every token of a tool result. Row-returning tools therefore
# emit one compact markdown table (column names appear once) preceded by a
# one-line metadata header stating the row count and whether more rows exist.
# No tool dumps an unbounded result set, and large values are summarised.
# ---------------------------------------------------------------------------


def _cell_text(value: Any) -> str:
    """Render one cell, keeping the table structure intact and the size bounded."""
    if value is None:
        return "null"
    text = str(format_value(value))
    return text.replace("|", "\\|").replace("\r", "").replace("\n", " ")


def render_rows(
    columns: List[str],
    rows: List[tuple],
    truncated: bool = False,
    note: Optional[str] = None,
) -> str:
    """Render rows as a metadata line plus a compact markdown table."""
    if not columns:
        return "no columns returned (the statement produced no result set)"
    meta = f"{len(rows)} row(s)"
    if truncated:
        meta += " (truncated; more rows exist)"
    meta += " | columns: " + ", ".join(columns)
    if note:
        meta += " | " + note
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = ["| " + " | ".join(_cell_text(value) for value in row) + " |" for row in rows]
    return "\n".join([meta, "", header, divider, *body])


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_IDENTIFIER_SEGMENT = r"[A-Za-z_][A-Za-z0-9_$#]*"
_TABLE_NAME_PATTERN = re.compile(rf"^{_IDENTIFIER_SEGMENT}(?:\.{_IDENTIFIER_SEGMENT})?$")
_SCHEMA_NAME_PATTERN = re.compile(rf"^{_IDENTIFIER_SEGMENT}$")
_COLUMN_NAME_PATTERN = re.compile(rf"^{_IDENTIFIER_SEGMENT}$")
_QUERY_PATTERN = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def validate_query(query: str) -> str:
    """Allow only a single read-only SELECT/WITH statement."""
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    query = query.strip().rstrip(";").strip()
    if ";" in query:
        raise ValueError("Only one SQL statement is allowed (no ';').")
    if not _QUERY_PATTERN.match(query):
        raise ValueError(
            "Only read-only SELECT/WITH queries are allowed. "
            "This server cannot run DDL, DML, or PL/SQL."
        )
    return query


def _validate_identifier(value: str, pattern: re.Pattern, kind: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{kind} cannot be empty")
    value = value.strip()
    if not pattern.match(value):
        raise ValueError(
            f"Invalid {kind}: '{value}'. Use only letters, digits, '_', '$', and '#' "
            "(dots allowed for a schema qualifier)."
        )
    return value.upper()


def validate_table_name(table_name: str) -> Tuple[Optional[str], str]:
    """Validate [schema.]table and return the (schema, table) pair, uppercased."""
    if not table_name or not table_name.strip():
        raise ValueError("Table name cannot be empty")
    table_name = table_name.strip()
    if not _TABLE_NAME_PATTERN.match(table_name):
        raise ValueError(
            f"Invalid table name: '{table_name}'. Table names must contain only letters, "
            "digits, '_', '$', and '#', optionally qualified as 'SCHEMA.TABLE'."
        )
    if "." in table_name:
        schema, table = table_name.split(".", 1)
        return schema.upper(), table.upper()
    return None, table_name.upper()


def validate_schema_name(schema: str) -> str:
    """Validate a schema/owner name."""
    return _validate_identifier(schema, _SCHEMA_NAME_PATTERN, "schema name")


def validate_column_name(column: str) -> str:
    """Validate a column name."""
    return _validate_identifier(column, _COLUMN_NAME_PATTERN, "column name")


def validate_max_rows(max_rows: int, cap: Optional[int] = None) -> int:
    """Validate a positive row cap and clamp it to the configured maximum."""
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError(f"max_rows must be a positive integer, got: {max_rows}")
    limit = cap if cap and cap > 0 else config.max_rows
    return min(max_rows, limit)


def quote_identifier(identifier: str) -> str:
    """Quote an already-validated identifier."""
    return f'"{identifier}"'


def qualified_name(schema: Optional[str], table: str) -> str:
    """Build a validated, quoted table reference."""
    if schema:
        return f"{quote_identifier(schema)}.{quote_identifier(table)}"
    return quote_identifier(table)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _run_query(query: str, max_rows: int) -> Tuple[List[str], List[tuple], bool]:
    """Run a read-only query, returning (columns, rows, truncated)."""
    query = validate_query(query)
    with get_oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [description[0] for description in (cursor.description or [])]
            if not columns:
                return [], [], False
            fetched = cursor.fetchmany(max_rows + 1)
            truncated = len(fetched) > max_rows
            return columns, fetched[:max_rows], truncated


def _fetch_columns(schema: Optional[str], table: str) -> List[Dict[str, Any]]:
    """Fetch column metadata for a table or view (current schema when schema is None)."""
    prefix = "all_" if schema else "user_"
    owner_predicate = "c.owner = :owner AND " if schema else ""
    binds: Dict[str, Any] = {"table_name": table}
    if schema:
        binds["owner"] = schema
    sql = f"""
        SELECT c.column_name, c.data_type, c.data_length, c.data_precision, c.data_scale,
               c.nullable, c.column_id
        FROM {prefix}tab_columns c
        WHERE {owner_predicate}c.table_name = :table_name
        ORDER BY c.column_id
    """
    with get_oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, binds)
            rows = cursor.fetchall()
    return [
        {
            "column_name": row[0],
            "data_type": row[1],
            "data_length": row[2],
            "data_precision": row[3],
            "data_scale": row[4],
            "nullable": row[5],
            "column_id": row[6],
        }
        for row in rows
    ]


def _table_exists(schema: Optional[str], table: str) -> bool:
    """Check for a table or a view with the given name."""
    prefix = "all_" if schema else "user_"
    owner_predicate = "owner = :owner AND " if schema else ""
    binds: Dict[str, Any] = {"table_name": table}
    if schema:
        binds["owner"] = schema
    sql = (
        f"SELECT COUNT(*) FROM ("
        f"SELECT 1 FROM {prefix}tables WHERE {owner_predicate}table_name = :table_name "
        f"UNION ALL "
        f"SELECT 1 FROM {prefix}views WHERE {owner_predicate}view_name = :table_name)"
    )
    with get_oracle_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, binds)
            (count,) = cursor.fetchone()
    return bool(count)


def _markdown_preview(columns: List[str], rows: List[tuple], limit: int = 5) -> str:
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = [
        "| " + " | ".join(_cell_text(value) for value in row) + " |"
        for row in rows[:limit]
    ]
    return "\n".join([header, divider, *body])


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    description=(
        "Executes a read-only SELECT/WITH query and returns a compact markdown table plus a "
        "metadata line (row count, and whether more rows exist). Results are preview-capped "
        "by default to protect the caller's context: aggregate in SQL and only pass max_rows "
        "when the raw rows are really needed. Large cell values are summarised."
    )
)
def execute_query(query: str, max_rows: Optional[int] = None) -> str:
    """Execute a read-only SQL query and return a compact, bounded preview."""
    if not config.user or not config.password:
        raise ValueError(
            "Oracle configuration is missing. Please set ORACLE_USER and ORACLE_PASSWORD "
            "environment variables."
        )
    if max_rows is not None:
        limit = validate_max_rows(max_rows)
    else:
        limit = min(config.preview_rows, config.max_rows)
    logger.info("Executing query", query_preview=query[:100], max_rows=limit)
    try:
        columns, rows, truncated = _run_query(query, limit)
        logger.info("Query executed successfully", row_count=len(rows), truncated=truncated)
        return render_rows(columns, rows, truncated=truncated)
    except (oracledb.Error, ValueError) as error:
        logger.error(
            "Query execution failed",
            error=str(error),
            exception_type=type(error).__name__,
        )
        raise


@mcp.tool(
    description=(
        "Retrieves a list of all tables and views available in the configured Oracle schema "
        "as a compact markdown table. Optionally takes a schema name."
    )
)
def list_tables(schema: Optional[str] = None) -> str:
    """List tables and views in the current schema (or a given schema)."""
    try:
        if schema:
            owner = validate_schema_name(schema)
            sql = """
                SELECT owner, table_name, 'TABLE' AS object_type FROM all_tables WHERE owner = :owner
                UNION ALL
                SELECT owner, view_name, 'VIEW' AS object_type FROM all_views WHERE owner = :owner
                ORDER BY 2
            """
            binds = {"owner": owner}
        else:
            sql = """
                SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AS owner, table_name, 'TABLE' AS object_type
                FROM user_tables
                UNION ALL
                SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA'), view_name, 'VIEW' FROM user_views
                ORDER BY 2
            """
            binds = {}
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, binds)
                columns, rows = _fetch_rows(cursor)
        result = render_rows(columns, rows)
        logger.info("Tables listed successfully", object_count=len(rows), schema=schema)
        return result
    except (oracledb.Error, ValueError) as error:
        logger.error("Failed to list tables", error=str(error), exception_type=type(error).__name__)
        raise


@mcp.tool(
    description=(
        "Retrieves the schema of a table or view as a compact markdown table: column name, "
        "data type, length, nullability, and whether the column is part of the primary key."
    )
)
def get_table_schema(table_name: str) -> str:
    """Get column metadata for a table or view."""
    schema, table = validate_table_name(table_name)
    logger.info("Getting table schema", table=table, schema=schema)
    try:
        prefix = "all_" if schema else "user_"
        owner_predicate = "c.owner = :owner AND " if schema else ""
        binds: Dict[str, Any] = {"table_name": table}
        if schema:
            binds["owner"] = schema
        sql = f"""
            SELECT c.column_name, c.data_type, c.data_length, c.data_precision, c.data_scale,
                   c.nullable,
                   CASE WHEN pk.column_name IS NOT NULL THEN 'YES' ELSE 'NO' END AS is_primary_key
            FROM {prefix}tab_columns c
            LEFT JOIN (
                SELECT cc.column_name
                FROM {prefix}constraints cst
                JOIN {prefix}cons_columns cc
                  ON cst.constraint_name = cc.constraint_name
                WHERE cst.constraint_type = 'P' AND cst.table_name = :table_name
                {"AND cst.owner = :owner" if schema else ""}
            ) pk ON pk.column_name = c.column_name
            WHERE {owner_predicate}c.table_name = :table_name
            ORDER BY c.column_id
        """
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, binds)
                columns, rows = _fetch_rows(cursor)
        if not rows:
            raise ValueError(f"Table or view '{table_name}' was not found or has no accessible columns.")
        projected = [tuple(row[index] for index in (0, 1, 2, 5, 6)) for row in rows]
        result = render_rows(
            ["COLUMN_NAME", "DATA_TYPE", "DATA_LENGTH", "NULLABLE", "PRIMARY_KEY"],
            projected,
        )
        logger.info("Schema retrieved successfully", table_name=table_name, column_count=len(rows))
        return result
    except (oracledb.Error, ValueError) as error:
        logger.error(
            "Failed to get table schema",
            table_name=table_name,
            error=str(error),
            exception_type=type(error).__name__,
        )
        raise


@mcp.tool(
    description=(
        "Retrieves a small sample of rows from the specified table as a compact markdown table. "
        "sample_size controls how many rows to return (default: 10, capped by the server)."
    )
)
def sample_table_data(table_name: str, sample_size: int = 10) -> str:
    """Fetch the first rows of a table."""
    schema, table = validate_table_name(table_name)
    limit = validate_max_rows(sample_size)
    logger.info("Sampling table data", table=table, schema=schema, sample_size=limit)
    try:
        if not _table_exists(schema, table):
            raise ValueError(f"Table '{table_name}' was not found.")
        sql = f"SELECT * FROM {qualified_name(schema, table)} FETCH FIRST {limit} ROWS ONLY"
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns, rows = _fetch_rows(cursor)
        result = render_rows(
            columns,
            rows,
            note=f"sample of {qualified_name(schema, table)}",
        )
        logger.info("Sample data retrieved successfully", table_name=table_name, row_count=len(rows))
        return result
    except (oracledb.Error, ValueError) as error:
        logger.error(
            "Failed to sample table data",
            table_name=table_name,
            error=str(error),
            exception_type=type(error).__name__,
        )
        raise


@mcp.tool(
    description=(
        "Retrieves table details: owner, tablespace, optimizer statistics (NUM_ROWS, BLOCKS, "
        "AVG_ROW_LEN, LAST_ANALYZED) and, optionally, an exact row count."
    )
)
def get_table_details(table_name: str, exact_row_count: bool = False) -> Dict[str, Any]:
    """Get table-level metadata and statistics."""
    schema, table = validate_table_name(table_name)
    logger.info("Getting table details", table=table, schema=schema, exact_row_count=exact_row_count)
    try:
        prefix = "all_" if schema else "user_"
        owner_predicate = "owner = :owner AND " if schema else ""
        owner_select = "owner" if schema else "SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') AS owner"
        binds: Dict[str, Any] = {"table_name": table}
        if schema:
            binds["owner"] = schema
        sql = f"""
            SELECT {owner_select}, table_name, tablespace_name, num_rows, blocks, avg_row_len,
                   last_analyzed, temporary, compression
            FROM {prefix}tables
            WHERE {owner_predicate}table_name = :table_name
        """
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, binds)
                row = cursor.fetchone()
                if row is None:
                    cursor.execute(
                        f"SELECT {owner_select}, view_name FROM {prefix}views WHERE {owner_predicate}view_name = :table_name",
                        binds,
                    )
                    view_row = cursor.fetchone()
                    if view_row is None:
                        raise ValueError(f"Table or view '{table_name}' was not found.")
                    details: Dict[str, Any] = {
                        "owner": view_row[0],
                        "name": view_row[1],
                        "object_type": "VIEW",
                    }
                else:
                    details = {
                        "owner": row[0],
                        "name": row[1],
                        "object_type": "TABLE",
                        "tablespace_name": row[2],
                        "num_rows_stat": row[3],
                        "blocks": row[4],
                        "avg_row_len": row[5],
                        "last_analyzed": format_value(row[6]),
                        "temporary": row[7],
                        "compression": row[8],
                    }
                if exact_row_count:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {qualified_name(schema, table)}"
                    )
                    (count,) = cursor.fetchone()
                    details["exact_row_count"] = count
        logger.info("Table details retrieved successfully", table_name=table_name)
        return details
    except (oracledb.Error, ValueError) as error:
        logger.error(
            "Failed to get table details",
            table_name=table_name,
            error=str(error),
            exception_type=type(error).__name__,
        )
        raise


_NUMERIC_TYPES = ("NUMBER", "FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE")
_DATE_TYPES = ("DATE", "TIMESTAMP")
_CHARACTER_TYPES = ("CHAR", "VARCHAR2", "NCHAR", "NVARCHAR2", "LONG")


def _profile_metrics(data_type: str) -> List[str]:
    """Pick the aggregate metrics worth computing for a column type."""
    data_type = (data_type or "").upper()
    if data_type.startswith(_NUMERIC_TYPES):
        return ["non_null", "distinct", "min", "max", "avg"]
    if data_type.startswith(_DATE_TYPES):
        return ["non_null", "distinct", "min", "max"]
    if data_type.startswith(_CHARACTER_TYPES):
        return ["non_null", "distinct", "min", "max"]
    return ["non_null"]


_METRIC_EXPRESSION = {
    "non_null": "COUNT({column})",
    "distinct": "COUNT(DISTINCT {column})",
    "min": "MIN({column})",
    "max": "MAX({column})",
    "avg": "AVG({column})",
}


@mcp.tool(
    description=(
        "Profiles a table for visualization: row count plus per-column statistics (non-null "
        "count, distinct count, min, max, average) to decide which chart fits the data."
    )
)
def profile_table(
    table_name: str, columns: Optional[List[str]] = None, max_columns: int = 50
) -> Dict[str, Any]:
    """Compute per-column statistics for a table or view."""
    schema, table = validate_table_name(table_name)
    if max_columns <= 0:
        raise ValueError(f"max_columns must be a positive integer, got: {max_columns}")
    max_columns = min(max_columns, 200)
    logger.info("Profiling table", table=table, schema=schema)
    try:
        table_columns = _fetch_columns(schema, table)
        if not table_columns:
            raise ValueError(f"Table or view '{table_name}' was not found.")
        if columns:
            wanted = [validate_column_name(column) for column in columns]
            available = {column["column_name"]: column for column in table_columns}
            missing = [column for column in wanted if column not in available]
            if missing:
                raise ValueError(f"Unknown column(s) for {table_name}: {', '.join(missing)}")
            selected = [available[column] for column in wanted]
        else:
            selected = table_columns
        truncated = len(selected) > max_columns
        selected = selected[:max_columns]

        select_parts = ["COUNT(*) AS TOTAL_ROWS"]
        metrics: List[Tuple[str, str]] = []
        for column in selected:
            quoted = quote_identifier(column["column_name"])
            for metric in _profile_metrics(column["data_type"]):
                select_parts.append(
                    f"{_METRIC_EXPRESSION[metric].format(column=quoted)} "
                    f'AS "{column["column_name"]}__{metric.upper()}"'
                )
                metrics.append((column["column_name"], metric))

        sql = f"SELECT {', '.join(select_parts)} FROM {qualified_name(schema, table)}"
        with get_oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Could not profile '{table_name}'.")
        row_count = row[0]
        profile: List[Dict[str, Any]] = []
        metric_values = iter(row[1:])
        for column in selected:
            entry: Dict[str, Any] = {
                "column": column["column_name"],
                "data_type": column["data_type"],
                "nullable": column["nullable"],
            }
            for _column, metric in [metric for metric in metrics if metric[0] == column["column_name"]]:
                value = next(metric_values)
                entry[metric] = format_value(value)
            entry["nulls"] = row_count - entry.get("non_null", 0)
            profile.append(entry)
        result = {
            "table": f"{schema}.{table}" if schema else table,
            "row_count": row_count,
            "columns": profile,
        }
        if truncated:
            result["note"] = (
                f"Only the first {max_columns} of {len(table_columns)} columns were profiled; "
                "pass the columns argument to choose others."
            )
        logger.info("Table profiled successfully", table_name=table_name, columns=len(profile))
        return result
    except (oracledb.Error, ValueError) as error:
        logger.error(
            "Failed to profile table",
            table_name=table_name,
            error=str(error),
            exception_type=type(error).__name__,
        )
        raise


@mcp.tool(
    description=(
        "Runs a read-only SQL query and renders the result as a chart image (PNG). "
        f"chart_type is one of: {', '.join(CHART_TYPES)}. The first column is the x-axis or "
        "labels; numeric columns after it become series. Returns the image plus a data preview."
    )
)
def create_chart(
    sql: str,
    chart_type: str,
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
) -> list:
    """Render a SQL result set as a PNG chart (returned as image + text preview)."""
    logger.info("Rendering chart", chart_type=chart_type, query_preview=sql[:100])
    try:
        columns, rows, truncated = _run_query(sql, config.max_rows)
        png = render_chart(columns, rows, chart_type, title=title, x_label=x_label, y_label=y_label)
    except (oracledb.Error, ValueError, ChartError) as error:
        logger.error("Chart rendering failed", error=str(error), exception_type=type(error).__name__)
        raise

    summary_lines = [
        f"Rendered a `{chart_type.lower()}` chart from the query result "
        f"({len(rows)} row{'s' if len(rows) != 1 else ''}, {len(columns)} column"
        f"{'s' if len(columns) != 1 else ''}).",
        "",
        f"SQL: {sql.strip()}",
    ]
    if truncated:
        summary_lines.append(f"Note: only the first {config.max_rows} rows were plotted.")
    summary_lines.extend(["", "First rows:", "", _markdown_preview(columns, rows)])
    summary = "\n".join(summary_lines)
    logger.info("Chart rendered successfully", chart_type=chart_type, row_count=len(rows))
    return [Image(data=png, format="png"), summary]
