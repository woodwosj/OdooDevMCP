"""Shared pytest fixtures for Odoo Dev MCP tests."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from pydantic_settings import BaseSettings


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock()

    # Server config
    config.server = Mock()
    config.server.name = "odoo-dev-mcp-test"
    config.server.version = "1.0.0"
    config.server.transport = "stdio"
    config.server.port = 8768
    config.server.log_level = "info"

    # Database config
    config.database = Mock()
    config.database.host = "localhost"
    config.database.port = 5432
    config.database.user = "odoo"
    config.database.password = "test_password"
    config.database.name = "test_db"
    config.database.pool_size = 5
    config.database.query_timeout = 30
    config.database.max_result_rows = 1000

    # Command config
    config.command = Mock()
    config.command.default_timeout = 30
    config.command.max_timeout = 600
    config.command.working_directory = "/tmp/test"

    # Filesystem config
    config.filesystem = Mock()
    config.filesystem.max_read_size_mb = 10
    config.filesystem.max_write_size_mb = 50

    # Phone home config
    config.phone_home = Mock()
    config.phone_home.url = None
    config.phone_home.heartbeat_interval = 60
    config.phone_home.retry_count = 3
    config.phone_home.retry_backoff = 2
    config.phone_home.timeout = 5
    config.phone_home.extra_metadata = {}

    # Logging config
    config.logging = Mock()
    config.logging.audit_log = "/tmp/audit.log"
    config.logging.server_log = "/tmp/server.log"
    config.logging.max_log_size_mb = 100
    config.logging.backup_count = 5

    # Odoo config
    config.odoo = Mock()
    config.odoo.config_path = "/etc/odoo/odoo.conf"
    config.odoo.service_name = "odoo"
    config.odoo.shell_command = "odoo shell"
    config.odoo.addons_paths = []

    return config


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()

    pool.getconn.return_value = conn
    conn.cursor.return_value = cursor

    return pool, conn, cursor


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create a temporary audit log file."""
    log_file = tmp_path / "audit.log"
    log_file.touch()
    return str(log_file)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess module for command execution tests."""
    mock = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset rate limiters between tests."""
    from odoo_dev_mcp.utils.security import command_limiter, query_limiter, shell_limiter

    command_limiter.calls = []
    query_limiter.calls = []
    shell_limiter.calls = []
    yield
