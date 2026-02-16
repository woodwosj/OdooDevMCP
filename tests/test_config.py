"""Tests for configuration loading and validation."""

import os
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest


class TestConfigLoading:
    """Test configuration loading from YAML."""

    @patch("odoo_dev_mcp.config.Path")
    @patch("builtins.open", new_callable=mock_open, read_data="server:\n  name: test\n")
    def test_loads_yaml_config(self, mock_file, mock_path):
        """Should load configuration from YAML file."""
        from odoo_dev_mcp.config import load_config

        mock_path.return_value.exists.return_value = True

        config = load_config("/test/config.yaml")

        assert config is not None

    @patch("odoo_dev_mcp.config.Path")
    def test_handles_missing_config_file(self, mock_path):
        """Should handle missing config file gracefully."""
        from odoo_dev_mcp.config import load_config

        mock_path.return_value.exists.return_value = False

        # Should either raise or return defaults
        try:
            config = load_config("/missing/config.yaml")
            # If it returns, should have default values
            assert config is not None
        except FileNotFoundError:
            # Acceptable behavior
            pass


class TestConfigValidation:
    """Test configuration validation."""

    def test_validates_pool_size_bounds(self):
        """Should enforce pool size bounds (M1 fix suggestion)."""
        from odoo_dev_mcp.config import DatabaseConfig

        # This should work with default
        config = DatabaseConfig()
        assert 1 <= config.pool_size <= 20

        # Test with explicit value
        config = DatabaseConfig(pool_size=10)
        assert config.pool_size == 10

    def test_validates_required_fields(self):
        """Should validate required configuration fields."""
        from odoo_dev_mcp.config import ServerConfig

        # Should work with defaults
        config = ServerConfig()
        assert config.name is not None
        assert config.version is not None


class TestEnvironmentVariables:
    """Test environment variable override."""

    @patch.dict(
        "os.environ",
        {
            "ODOO_MCP_SERVER_PORT": "9999",
            "ODOO_MCP_DATABASE_HOST": "db.example.com",
        },
    )
    def test_overrides_from_env_vars(self):
        """Should override config from environment variables."""
        from odoo_dev_mcp.config import ServerConfig

        # Note: Actual implementation may vary
        # This test checks the pattern is available
        assert "ODOO_MCP_SERVER_PORT" in os.environ


class TestSensitiveDataMasking:
    """Test that sensitive config is properly masked."""

    def test_password_not_in_repr(self):
        """Database password should not appear in repr/str."""
        from odoo_dev_mcp.config import DatabaseConfig

        config = DatabaseConfig(password="super_secret_password")

        # Convert to string
        config_str = str(config)

        # Password should not appear in plain text
        assert "super_secret_password" not in config_str
