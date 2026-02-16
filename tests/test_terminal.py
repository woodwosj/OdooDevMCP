"""Tests for terminal command execution tool."""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from OdooDevMCP.tools.terminal import execute_command


class TestExecuteCommand:
    """Test execute_command(env, command, ...)."""

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_executes_simple_command(self, mock_run, mock_env):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hello"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = execute_command(mock_env, "echo hello")

        assert result["exit_code"] == 0
        assert result["stdout"] == "hello"
        assert result["stderr"] == ""
        assert result["timed_out"] is False
        assert "duration_ms" in result

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_handles_timeout(self, mock_run, mock_env):
        timeout_exc = subprocess.TimeoutExpired("test", 5)
        timeout_exc.stdout = b"partial output"
        timeout_exc.stderr = b"partial error"
        mock_run.side_effect = timeout_exc

        result = execute_command(mock_env, "sleep 100", timeout=5)

        assert result["exit_code"] == -1
        assert result["timed_out"] is True
        assert result["stdout"] == "partial output"
        assert result["stderr"] == "partial error"

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_handles_timeout_with_none_output(self, mock_run, mock_env):
        timeout_exc = subprocess.TimeoutExpired("test", 5)
        timeout_exc.stdout = None
        timeout_exc.stderr = None
        mock_run.side_effect = timeout_exc

        result = execute_command(mock_env, "sleep 100", timeout=5)

        assert result["timed_out"] is True
        assert result["stdout"] == ""
        assert result["stderr"] == ""

    def test_enforces_rate_limit(self, mock_env):
        """After 10 calls, rate limit should kick in."""
        with patch("OdooDevMCP.tools.terminal.subprocess.run") as mock_run:
            mock_result = Mock(returncode=0, stdout="", stderr="")
            mock_run.return_value = mock_result

            for _ in range(10):
                execute_command(mock_env, "echo ok")

            with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                execute_command(mock_env, "echo blocked")

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_respects_max_timeout(self, mock_run, mock_env):
        """Timeout should be clamped to max_timeout from ICP."""
        mock_env._icp_store["mcp.command_max_timeout"] = "100"

        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = mock_result

        execute_command(mock_env, "echo test", timeout=999)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 100

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_uses_custom_env_vars(self, mock_run, mock_env):
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = mock_result

        execute_command(mock_env, "echo test", env_vars={"CUSTOM_VAR": "value"})

        call_kwargs = mock_run.call_args[1]
        assert "CUSTOM_VAR" in call_kwargs["env"]
        assert call_kwargs["env"]["CUSTOM_VAR"] == "value"

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_uses_custom_working_directory(self, mock_run, mock_env):
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = mock_result

        execute_command(mock_env, "ls", working_directory="/custom/dir")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/custom/dir"

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_default_working_directory(self, mock_run, mock_env):
        """When no working_directory is given, should default to /opt/odoo."""
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = mock_result

        execute_command(mock_env, "ls")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/opt/odoo"

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_general_exception_handling(self, mock_run, mock_env):
        """Non-timeout exceptions should return exit_code -2."""
        mock_run.side_effect = OSError("Permission denied")

        result = execute_command(mock_env, "bad_cmd")

        assert result["exit_code"] == -2
        assert "Permission denied" in result["stderr"]

    @patch("OdooDevMCP.tools.terminal.subprocess.run")
    def test_zero_timeout_means_no_timeout(self, mock_run, mock_env):
        """timeout=0 should translate to None (no timeout)."""
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = mock_result

        execute_command(mock_env, "echo test", timeout=0)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] is None
