"""Tests for terminal command execution."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from odoo_dev_mcp.tools.terminal import execute_command


class TestExecuteCommand:
    """Test terminal command execution."""

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_executes_simple_command(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should execute command and return results."""
        mock_get_config.return_value = mock_config

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = execute_command("echo test")

        assert result["exit_code"] == 0
        assert result["stdout"] == "output"
        assert result["stderr"] == ""
        assert result["timed_out"] is False
        mock_audit.assert_called_once()

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_handles_timeout(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should handle timeout and kill process (H4 fix)."""
        mock_get_config.return_value = mock_config

        # Simulate timeout
        timeout_exc = subprocess.TimeoutExpired("test", 5)
        timeout_exc.stdout = b"partial output"
        timeout_exc.stderr = b"partial error"
        mock_run.side_effect = timeout_exc

        with patch("odoo_dev_mcp.tools.terminal.subprocess.run") as mock_pkill:
            result = execute_command("sleep 100", timeout=5)

        assert result["exit_code"] == -1
        assert result["timed_out"] is True
        assert result["stdout"] == "partial output"
        assert result["stderr"] == "partial error"

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    @patch("odoo_dev_mcp.tools.terminal.command_limiter")
    def test_enforces_rate_limit(
        self, mock_limiter, mock_audit, mock_get_config, mock_run, mock_config
    ):
        """Should enforce rate limiting (H3 fix)."""
        mock_get_config.return_value = mock_config
        mock_limiter.allow.return_value = False

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            execute_command("echo test")

        mock_run.assert_not_called()

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_respects_max_timeout(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should clamp timeout to max_timeout."""
        mock_get_config.return_value = mock_config
        mock_config.command.max_timeout = 100

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        execute_command("echo test", timeout=999)

        # Should call subprocess with clamped timeout
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 100

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_uses_custom_env_vars(self, mock_audit, mock_get_config, mock_run, mock_config):
        """Should merge custom environment variables."""
        mock_get_config.return_value = mock_config

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        execute_command("echo test", env={"CUSTOM_VAR": "value"})

        call_kwargs = mock_run.call_args[1]
        assert "CUSTOM_VAR" in call_kwargs["env"]
        assert call_kwargs["env"]["CUSTOM_VAR"] == "value"

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_uses_custom_working_directory(
        self, mock_audit, mock_get_config, mock_run, mock_config
    ):
        """Should use custom working directory."""
        mock_get_config.return_value = mock_config

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        execute_command("ls", working_directory="/custom/dir")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/custom/dir"
