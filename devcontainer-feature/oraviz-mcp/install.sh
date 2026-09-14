#!/usr/bin/env bash
set -e

# The 'install.sh' entrypoint script is always executed as the root user

# Variable declarations from feature options
VERSION="${VERSION:-"latest"}"
ORACLE_USER="${ORACLEUSER}"
ORACLE_PASSWORD="${ORACLEPASSWORD}"
ORACLE_HOST="${ORACLEHOST}"
ORACLE_PORT="${ORACLEPORT}"
ORACLE_SERVICE="${ORACLESERVICE}"
ORAVIZ_MCP_REPO="${ORAVIZMCPREPO}"

echo "Setting up Oracle Viz MCP Server..."

# Setup the server directory
mkdir -p /opt/oraviz-mcp
cd /opt/oraviz-mcp

if [ "${VERSION}" = "latest" ]; then
    echo "Cloning the latest version of OraViz MCP Server from ${ORAVIZ_MCP_REPO}..."
    git clone ${ORAVIZ_MCP_REPO} .
else
    echo "Cloning version ${VERSION} of OraViz MCP Server from ${ORAVIZ_MCP_REPO}..."
    git clone --depth 1 --branch ${VERSION} ${ORAVIZ_MCP_REPO} .
fi

INSTALL_WITH_SUDO="false"
if command -v sudo >/dev/null 2>&1; then
    if [ "root" != "$_REMOTE_USER" ]; then
        INSTALL_WITH_SUDO="true"
    fi
fi

ENV_PATH=/home/$_REMOTE_USER/.oraviz-mcp-env

if [ "${INSTALL_WITH_SUDO}" = "true" ]; then
    sudo -u ${_REMOTE_USER} bash -c "echo 'ORACLE_USER=$ORACLE_USER' >> $ENV_PATH"
    sudo -u ${_REMOTE_USER} bash -c "echo 'ORACLE_PASSWORD=$ORACLE_PASSWORD' >> $ENV_PATH"
    sudo -u ${_REMOTE_USER} bash -c "echo 'ORACLE_HOST=$ORACLE_HOST' >> $ENV_PATH"
    sudo -u ${_REMOTE_USER} bash -c "echo 'ORACLE_PORT=$ORACLE_PORT' >> $ENV_PATH"
    sudo -u ${_REMOTE_USER} bash -c "echo 'ORACLE_SERVICE=$ORACLE_SERVICE' >> $ENV_PATH"
else
    echo ORACLE_USER=$ORACLE_USER >> $ENV_PATH || true
    echo ORACLE_PASSWORD=$ORACLE_PASSWORD >> $ENV_PATH || true
    echo ORACLE_HOST=$ORACLE_HOST >> $ENV_PATH || true
    echo ORACLE_PORT=$ORACLE_PORT >> $ENV_PATH || true
    echo ORACLE_SERVICE=$ORACLE_SERVICE >> $ENV_PATH || true
fi

# The env file holds credentials: keep it readable only by its owner.
chmod 600 "$ENV_PATH" 2>/dev/null || true
