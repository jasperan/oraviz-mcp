#!/usr/bin/env python
"""
Oracle Viz MCP Server - Application Entry Point
Handles environment setup, configuration validation, and server startup.
"""

from __future__ import annotations

import sys

import dotenv
import structlog

from oraviz_mcp.server import TransportType, config, mcp

logger = structlog.get_logger()


def setup_environment() -> bool:
    """Set up and validate the environment configuration.

    Returns:
        bool: True if configuration is valid, False otherwise
    """
    if dotenv.load_dotenv():
        logger.info("Loaded environment variables from .env file")
    else:
        logger.info("No .env file found, using system environment variables")

    if not config.user:
        logger.error(
            "Missing required configuration",
            variable="ORACLE_USER",
            example="system",
        )
        return False

    if not config.password:
        logger.error(
            "Missing required configuration",
            variable="ORACLE_PASSWORD",
            hint="Password for ORACLE_USER (never logged)",
        )
        return False

    mcp_config = config.mcp_server_config
    if mcp_config:
        if str(mcp_config.mcp_server_transport).lower() not in TransportType.values():
            logger.error(
                "Invalid MCP transport",
                transport=mcp_config.mcp_server_transport,
                valid_transports=TransportType.values(),
            )
            return False

        try:
            if mcp_config.mcp_bind_port and not 1 <= int(mcp_config.mcp_bind_port) <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            logger.error(
                "Invalid MCP port",
                port=mcp_config.mcp_bind_port,
                expected="integer between 1 and 65535",
            )
            return False

    logger.info(
        "Oracle configuration loaded",
        host=config.host,
        port=config.port,
        service=config.service,
        user=config.user,
        dsn=config.connection_dsn(),
        max_rows=config.max_rows,
    )
    return True


def run_server():
    """Main entry point for the Oracle Viz MCP Server."""
    logger.info("Starting Oracle Viz MCP Server")

    if not setup_environment():
        logger.error("Environment setup failed, exiting")
        sys.exit(1)

    mcp_config = config.mcp_server_config
    transport = mcp_config.mcp_server_transport

    http_transports = [
        TransportType.HTTP.value,
        TransportType.SSE.value,
        TransportType.STREAMABLE_HTTP.value,
    ]
    if transport in http_transports:
        logger.info(
            "Starting server with network transport",
            transport=transport,
            host=mcp_config.mcp_bind_host,
            port=mcp_config.mcp_bind_port,
        )
        mcp.run(transport=transport, host=mcp_config.mcp_bind_host, port=int(mcp_config.mcp_bind_port))
    else:
        logger.info("Starting server with stdio transport", transport=transport)
        mcp.run(transport=transport)


if __name__ == "__main__":
    run_server()
