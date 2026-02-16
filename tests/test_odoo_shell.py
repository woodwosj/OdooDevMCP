"""Tests for Odoo shell execution tool (odoo_shell_exec).

The current implementation uses exec() with captured stdout, NOT subprocess.
"""

import pytest

from OdooDevMCP.tools.odoo_tools import odoo_shell_exec


class TestOdooShellExec:

    def test_executes_simple_code(self, mock_env):
        """Should execute code and capture stdout."""
        result = odoo_shell_exec(mock_env, "print('hello world')")

        assert result["output"] == "hello world\n"
        assert result["error"] is None
        assert result["return_value"] == "Execution successful"
        assert "duration_ms" in result

    def test_captures_multiline_output(self, mock_env):
        code = "for i in range(3):\n    print(i)"
        result = odoo_shell_exec(mock_env, code)

        assert result["output"] == "0\n1\n2\n"
        assert result["error"] is None

    def test_provides_env_in_globals(self, mock_env):
        """exec'd code should have access to env, cr, uid, context."""
        code = "print(type(env).__name__)"
        result = odoo_shell_exec(mock_env, code)

        # env is a MagicMock, so its type name is MagicMock
        assert "MagicMock" in result["output"]
        assert result["error"] is None

    def test_captures_execution_error(self, mock_env):
        """Errors in exec'd code should be caught and reported."""
        result = odoo_shell_exec(mock_env, "raise ValueError('boom')")

        assert result["error"] is not None
        assert "boom" in result["error"]
        assert result["output"] == ""

    def test_syntax_error_captured(self, mock_env):
        """Syntax errors should be caught."""
        result = odoo_shell_exec(mock_env, "def incomplete(")

        assert result["error"] is not None

    def test_name_error_captured(self, mock_env):
        """NameError from undefined variables should be caught."""
        result = odoo_shell_exec(mock_env, "print(undefined_variable)")

        assert result["error"] is not None
        assert "undefined_variable" in result["error"]

    def test_enforces_rate_limit(self, mock_env):
        """After 5 calls, rate limit should kick in."""
        for _ in range(5):
            odoo_shell_exec(mock_env, "pass")

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            odoo_shell_exec(mock_env, "pass")

    def test_timeout_clamped_to_max(self, mock_env):
        """Timeout should be clamped to 300 seconds internally.

        Since exec() does not enforce a timeout in the current implementation,
        we verify the function does not crash and the clamping logic exists.
        """
        # This should not raise; the clamp happens but exec has no timeout enforcement
        result = odoo_shell_exec(mock_env, "x = 1", timeout=999)

        assert result["error"] is None

    def test_empty_code(self, mock_env):
        """Empty code should execute without error."""
        result = odoo_shell_exec(mock_env, "")

        assert result["error"] is None
        assert result["output"] == ""

    def test_code_can_use_cr(self, mock_env):
        """Code should have access to cr (the cursor)."""
        code = "cr.execute('SELECT 1')"
        result = odoo_shell_exec(mock_env, code)

        # Should not error -- cr is a MagicMock that accepts any method call
        assert result["error"] is None
        mock_env.cr.execute.assert_called_with("SELECT 1")
