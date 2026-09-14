# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-14

### Added

- Minimal, visualization-first MCP server for Oracle AI Database (26ai Free included), modeled on
  [pab1it0/adx-mcp-server](https://github.com/pab1it0/adx-mcp-server).
- Tools: `execute_query`, `list_tables`, `get_table_schema`, `sample_table_data`, `get_table_details`,
  `profile_table`, `create_chart`.
- Context engineering: preview-capped results, one compact markdown table per result set with a metadata
  header, summarized large values (CLOB/BLOB/VECTOR), and per-column profiling instead of raw dumps.
- Chart rendering (bar, line, area, scatter, pie, histogram) to PNG via matplotlib, returned as MCP image
  content together with a short data preview.
- Read-only SQL enforcement, identifier validation, row and cell caps, and safe connection handling
  through python-oracledb thin mode (no Oracle client libraries required).
- stdio, http, sse, and streamable-http transports; structured JSON logging on stderr.
- Hermetic unit suite (98% coverage, `fail_under = 90`) plus live Oracle integration tests.
- Packaging: Dockerfile (multi-stage, non-root), CI workflow, MCP registry `server.json`, Smithery config,
  dev container feature, and a ready-to-run demo schema in `examples/demo-sales.sql`.
