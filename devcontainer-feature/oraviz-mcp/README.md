# Oracle Viz MCP Server Dev Container Feature

This dev container feature installs and configures the Oracle Viz Model Context Protocol (MCP) server for development purposes.

## Description

This feature sets up everything needed to run and develop with an Oracle Viz MCP server:

- Clones the server source into `/opt/oraviz-mcp`
- Sets up Docker CLI for container management
- Writes Oracle connection settings to `~/.oraviz-mcp-env` for the MCP client

## Usage

```json
"features": {
    "ghcr.io/jasperan/oraviz-mcp/oraviz-mcp:latest": {
        "version": "latest",
        "oracleUser": "system",
        "oracleHost": "localhost",
        "oraclePort": "1521",
        "oracleService": "FREEPDB1"
    }
}
```

Provide `ORACLE_PASSWORD` at runtime (the dev container writes it to `~/.oraviz-mcp-env` when the option is set,
but prefer injecting it from your environment rather than committing it).
