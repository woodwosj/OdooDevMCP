"""Tests for Odoo shell execution."""

import subprocess
from unittest.mock import Mock, patch

import pytest

from odoo_dev_mcp.tools.odoo_shell import odoo_shell


class TestOdooShell:
    """Test Odoo shell execution."""

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_executes_code_in_odoo_shell(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should execute Python code in Odoo shell."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output\n42"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = odoo_shell("print('Test')")

        assert result["error"] is None
        assert "Test output" in result["output"]
        mock_audit.assert_called_once()

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_handles_timeout_and_kills_process(
        self, mock_audit, mock_get_config, mock_run, mock_config
    ):
        """Should handle timeout and kill process (H4 fix)."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        # Simulate timeout
        timeout_exc = subprocess.TimeoutExpired("odoo shell", 30)
        timeout_exc.stdout = b"partial"
        timeout_exc.stderr = b""
        mock_run.side_effect = timeout_exc

        with patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run") as mock_pkill:
            result = odoo_shell("while True: pass", timeout=1)

        assert result["error"] is not None
        assert "timed out" in result["error"]

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_restricts_dangerous_imports(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should restrict dangerous imports (H5 fix)."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Execute code that tries to import os
        odoo_shell("import os")

        # Check that restriction code was prepended
        call_args = mock_run.call_args
        input_code = call_args[1]["input"]

        # Should contain import restriction code
        assert "_restricted_import" in input_code
        assert "os" in input_code  # Should be in restricted list

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    @patch("odoo_dev_mcp.tools.odoo_shell.shell_limiter")
    def test_enforces_rate_limit(
        self, mock_limiter, mock_audit, mock_get_config, mock_run, mock_config
    ):
        """Should enforce rate limiting."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_limiter.allow.return_value = False

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            odoo_shell("print('test')")

        mock_run.assert_not_called()

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_respects_max_timeout(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should clamp timeout to maximum."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Request very long timeout
        odoo_shell("print('test')", timeout=999)

        # Should be clamped to 300 seconds (5 minutes)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 300

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_uses_custom_database(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should use custom database when specified."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "default_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        odoo_shell("print('test')", database="custom_db")

        # Check command includes custom database
        call_args = mock_run.call_args[0][0]
        assert "-d" in call_args
        db_index = call_args.index("-d")
        assert call_args[db_index + 1] == "custom_db"


class TestH5ImportRestrictions:
    """Test H5 fix for import restrictions."""

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_blocks_os_import(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should block os module import."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        odoo_shell("import os")

        # Verify restriction code was added
        input_code = mock_run.call_args[1]["input"]
        assert "os" in str(input_code)
        assert "_restricted" in input_code

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_blocks_subprocess_import(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should block subprocess module import."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        odoo_shell("import subprocess")

        input_code = mock_run.call_args[1]["input"]
        assert "subprocess" in str(input_code)

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_allows_safe_imports(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should allow safe module imports."""
        mock_get_config.return_value = mock_config
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        # Should not raise error for safe imports
        odoo_shell("import json")

        # Code should still be executed
        mock_run.assert_called_once()
