# Oracle Viz MCP Testing Guide

This document describes how the Oracle Viz MCP server is tested.

## Testing Philosophy

1. **Hermetic by default** - the unit suite never touches a database; `python-oracledb` is mocked.
2. **Live proof on demand** - integration tests run real SQL against a real Oracle AI Database and are skipped unless `ORAVIZ_TEST_DSN` is set.
3. **Both paths per tool** - every tool has success and failure tests (guards, missing objects, database errors).
4. **The context contract is tested** - result rendering is asserted to stay compact and bounded.

## Test Structure

### Unit tests (no database)

- `tests/test_config.py` - `OracleConfig`, `MCPServerConfig`, transport enum, env parsing
- `tests/test_validation.py` - read-only SQL guard, identifier validation, row caps, value formatting, `render_rows`
- `tests/test_charts.py` - every chart type plus its validation errors (Agg backend, headless)
- `tests/test_server_tools.py` - all seven MCP tools against a scripted fake cursor
- `tests/test_main.py` - environment validation and transport selection

### Integration tests (live Oracle)

- `tests/integration/test_oracle_integration.py` - creates a scratch table, then exercises
  `execute_query`, `list_tables`, `get_table_schema`, `sample_table_data`, `get_table_details`,
  `profile_table`, `create_chart`, the write guard, and a `VECTOR(4, FLOAT32)` round trip.

## Running the Suite

```bash
# Everything hermetic (unit + skipped integration), with coverage
uv sync --extra dev
uv run pytest

# One file or one test
uv run pytest tests/test_server_tools.py -v
uv run pytest tests/test_charts.py::TestRenderChart::test_all_types_render_png

# Live integration against a local 26ai Free container
docker run -d --name oraviz-oracle -p 1530:1521 -e ORACLE_PWD=OraViz2026 \
  container-registry.oracle.com/database/free:latest
export ORAVIZ_TEST_DSN=localhost:1530/FREEPDB1
export ORAVIZ_TEST_USER=oraviz
export ORAVIZ_TEST_PASSWORD=OraViz2026
uv run pytest tests/integration -v --no-cov
```

Coverage is configured in `pyproject.toml` (`fail_under = 90`); the unit suite is what owns that gate.
Run integration-only sessions with `--no-cov` so the partial run does not trip it.

## Mocking Approach

`tests/test_server_tools.py` defines `FakeCursor`/`FakeConnection` helpers. Each `execute()` pops the
next scripted step (`description`, `rows`, `one`, or `raise`), which lets a test drive multi-query flows
(such as `get_table_details`' view fallback or `profile_table`'s metadata-then-aggregate) without a database.

## Adding New Tests

1. Add unit tests for the new behavior first, including the failure path.
2. Keep database access behind the `db`/`configured` fixtures in the integration module.
3. If a new tool returns rows, assert that its output stays compact (metadata line + markdown table).

## Continuous Integration

`.github/workflows/ci.yml` runs the unit suite with coverage on Python 3.12, builds the distribution,
and builds the Docker image so the container path is exercised too.
