"""Conservative SQL admission rules; database grants are the security boundary.

This deliberately accepts a subset of Oracle SELECT syntax. It is not a SQL
parser or a proof that a view, synonym, or built-in has no side effects.
"""

import re

MAX_SQL_CHARS = 32_000
_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>--[^\n]*(?:\n|$)|/\*.*?\*/)"
    r"|(?P<string>'(?:''|[^'])*')|(?P<quoted>\"(?:\"\"|[^\"])*\")"
    r"|(?P<word>[A-Za-z_][A-Za-z0-9_$#]*)|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<symbol>[(),.*+\-/=<>&|!:;%@])",
    re.DOTALL,
)
_FORBIDDEN = frozenset(
    "INSERT UPDATE DELETE MERGE CREATE ALTER DROP TRUNCATE GRANT REVOKE "
    "BEGIN DECLARE EXECUTE CALL COMMIT ROLLBACK SAVEPOINT LOCK INTO "
    "FUNCTION PROCEDURE PRAGMA NEXTVAL CURRVAL".split()
)
# Review additions as code changes. Never take function names from a tool input.
_FUNCTIONS = frozenset(
    "COUNT SUM AVG MIN MAX MEDIAN STDDEV VARIANCE ROUND TRUNC ABS CEIL FLOOR "
    "MOD POWER SQRT EXP LN LOG SIGN NVL NVL2 NULLIF COALESCE DECODE CAST "
    "TO_CHAR TO_DATE TO_TIMESTAMP TO_NUMBER UPPER LOWER LENGTH SUBSTR TRIM "
    "LTRIM RTRIM REPLACE CONCAT INSTR REGEXP_LIKE REGEXP_REPLACE REGEXP_SUBSTR "
    "EXTRACT ADD_MONTHS MONTHS_BETWEEN LAST_DAY ROW_NUMBER RANK DENSE_RANK "
    "LAG LEAD FIRST_VALUE LAST_VALUE LISTAGG GROUPING GROUPING_ID "
    "VECTOR_DISTANCE COSINE_DISTANCE L2_DISTANCE INNER_PRODUCT TO_VECTOR "
    "FROM_VECTOR VECTOR_DIMENSION_COUNT VECTOR_DIMENSION_FORMAT "
    "NTILE PERCENTILE_CONT PERCENTILE_DISC CUME_DIST PERCENT_RANK NTH_VALUE "
    "STDDEV_POP STDDEV_SAMP VAR_POP VAR_SAMP CORR COVAR_POP COVAR_SAMP "
    "GREATEST LEAST INITCAP LPAD RPAD TRANSLATE ASCII CHR REGEXP_COUNT REGEXP_INSTR "
    "NEXT_DAY NUMTODSINTERVAL NUMTOYMINTERVAL TO_DSINTERVAL TO_YMINTERVAL "
    "TO_TIMESTAMP_TZ SIN COS TAN ASIN ACOS ATAN ATAN2 BITAND "
    "APPROX_COUNT_DISTINCT ANY_VALUE".split()
)
_PAREN_KEYWORDS = frozenset(
    "AS IN EXISTS OVER PARTITION VALUES GROUPING SETS ROLLUP CUBE "
    "AND OR NOT WHEN THEN ELSE ON WHERE HAVING BY SELECT FROM JOIN "
    # Reserved words: Oracle cannot parse them as routine names.
    "USING GROUP DISTINCT UNION INTERSECT MINUS ALL ANY SOME LIKE BETWEEN".split()
)
# Data types that may carry a precision, e.g. CAST(x AS NUMBER(10, 2)).
_CAST_TYPES = frozenset(
    "NUMBER NUMERIC DECIMAL DEC FLOAT CHAR NCHAR VARCHAR VARCHAR2 NVARCHAR2 RAW "
    "TIMESTAMP VECTOR".split()
)


def _closing_paren(tokens, index):
    """Index of the parenthesis closing the one at tokens[index], or None."""
    depth = 0
    for position in range(index, len(tokens)):
        if tokens[position][0] == "symbol":
            depth += tokens[position][1] == "("
            depth -= tokens[position][1] == ")"
            if depth == 0:
                return position
    return None


def _is_cast_type(tokens, index, openers) -> bool:
    """True for the precision list of a type directly inside CAST(... AS type(...))."""
    return (
        tokens[index - 1][1] in _CAST_TYPES
        and index > 1
        and tokens[index - 2] == ("word", "AS")
        and bool(openers)
        and openers[-1] == "CAST"
    )


def _is_cte_column_list(tokens, index, depth, with_headers) -> bool:
    """True for ``name (col, ...) AS (`` in a WITH clause (required by recursive CTEs)."""
    if depth not in with_headers or index < 2:
        return False
    if tokens[index - 2] != ("word", "WITH") and tokens[index - 2] != ("symbol", ","):
        return False
    close = _closing_paren(tokens, index)
    return (
        close is not None
        and all(kind == "word" or value == "," for kind, value in tokens[index + 1 : close])
        and close + 1 < len(tokens)
        and tokens[close + 1] == ("word", "AS")
    )


def validate_query(query: str) -> str:
    """Admit one SELECT/CTE, rejecting writes, links, and unreviewed calls."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query cannot be empty")
    if len(query) > MAX_SQL_CHARS:
        raise ValueError(f"Query exceeds {MAX_SQL_CHARS} characters")
    query = query.strip()
    tokens = []
    pos = 0
    terminator = None
    while pos < len(query):
        match = _TOKEN.match(query, pos)
        if match is None:
            raise ValueError("Unsupported SQL syntax")
        kind, value = match.lastgroup, match.group()
        if query.startswith("/*", pos) and kind != "comment":
            raise ValueError("Unterminated SQL comment")
        if kind not in {"space", "comment"}:
            tokens.append((kind, value.upper() if kind == "word" else value))
            if value == ";":
                terminator = pos
        pos = match.end()

    if tokens and tokens[-1] == ("symbol", ";"):
        tokens.pop()
        # A trailing comment is allowed, but never forward the terminator.
        query = query[:terminator].rstrip()
    if not tokens or tokens[0] not in {("word", "SELECT"), ("word", "WITH")}:
        raise ValueError("Only read-only SELECT/WITH queries are allowed")

    depth = 0
    openers = []  # name of the word before each open parenthesis
    with_headers = set()  # depths currently inside a WITH clause's CTE list
    for index, (kind, value) in enumerate(tokens):
        if kind == "word" and value == "WITH":
            with_headers.add(depth)
        elif kind == "word" and value == "SELECT":
            with_headers.discard(depth)
        if kind == "word" and value in _FORBIDDEN:
            raise ValueError("Only read-only SQL without side-effecting constructs is allowed")
        if kind == "quoted" and value[1:-1].upper() in {"NEXTVAL", "CURRVAL"}:
            raise ValueError("Sequence access is prohibited")
        if kind == "word" and value in {"Q", "NQ"} and index + 1 < len(tokens) and tokens[index + 1][0] == "string":
            raise ValueError("Alternative quoted strings are not supported; use standard SQL strings")
        if kind == "symbol" and value in {";", "@", ":"}:
            raise ValueError("Multiple statements, database links, and unbound parameters are prohibited")
        if value == "(" and kind == "symbol":
            if index and tokens[index - 1][0] in {"word", "quoted"}:
                previous_kind, previous = tokens[index - 1]
                qualified = index > 1 and tokens[index - 2] == ("symbol", ".")
                if previous_kind == "quoted" or qualified or previous not in _FUNCTIONS | _PAREN_KEYWORDS:
                    if not (
                        previous_kind == "word"
                        and not qualified
                        and (
                            _is_cast_type(tokens, index, openers)
                            or _is_cte_column_list(tokens, index, depth, with_headers)
                        )
                    ):
                        raise ValueError("SQL function or construct is not on the reviewed allowlist")
            openers.append(tokens[index - 1][1] if index and tokens[index - 1][0] == "word" else None)
            depth += 1
            if depth > 32:
                raise ValueError("SQL nesting exceeds the limit")
        elif value == ")" and kind == "symbol":
            with_headers.discard(depth)
            if openers:
                openers.pop()
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced SQL parentheses")
    if depth:
        raise ValueError("Unbalanced SQL parentheses")
    return query
