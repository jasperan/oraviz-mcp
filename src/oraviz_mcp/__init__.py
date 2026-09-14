"""Oracle Viz MCP - a minimal, visualization-first MCP server for Oracle AI Database."""

__version__ = "0.1.0"

from oraviz_mcp.server import config, mcp  # noqa: F401

__all__ = ["config", "mcp", "__version__"]
