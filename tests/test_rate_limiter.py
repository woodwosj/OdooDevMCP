"""Tests for rate limiting functionality (H3)."""

import time
from unittest.mock import Mock, patch

import pytest

from odoo_dev_mcp.utils.security import RateLimiter, command_limiter, query_limiter, shell_limiter


class TestRateLimiterBasics:
    """Test basic rate limiter functionality."""

    def test_allows_requests_within_limit(self):
        """Should allow requests up to the limit."""
        limiter = RateLimiter(max_calls=3, period=60)

        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False

    def test_resets_after_time_period(self):
        """Should reset after the time period elapses."""
        limiter = RateLimiter(max_calls=2, period=0.05)  # 50ms

        # Use up limit
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False

        # Wait for period to pass
        time.sleep(0.06)

        # Should allow again
        assert limiter.allow() is True

    def test_sliding_window_behavior(self):
        """Should implement sliding window (not fixed window)."""
        limiter = RateLimiter(max_calls=2, period=0.1)

        # First call at t=0
        assert limiter.allow() is True
        time.sleep(0.03)

        # Second call at t=30ms
        assert limiter.allow() is True
        time.sleep(0.03)

        # Third call at t=60ms (should fail, first call still in window)
        assert limiter.allow() is False
        time.sleep(0.05)

        # Fourth call at t=110ms (should succeed, first call expired)
        assert limiter.allow() is True


class TestRateLimiterThreadSafety:
    """Test thread safety of rate limiter."""

    def test_concurrent_access(self):
        """Should handle concurrent access safely."""
        import threading

        limiter = RateLimiter(max_calls=5, period=60)
        results = []
        lock = threading.Lock()

        def make_request():
            allowed = limiter.allow()
            with lock:
                results.append(allowed)

        # Create 10 threads
        threads = [threading.Thread(target=make_request) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Should have exactly 5 True and 5 False
        assert results.count(True) == 5
        assert results.count(False) == 5

    def test_no_race_conditions(self):
        """Should not have race conditions in call tracking."""
        import threading

        limiter = RateLimiter(max_calls=100, period=1)

        def make_many_calls():
            for _ in range(10):
                limiter.allow()

        # Multiple threads making calls
        threads = [threading.Thread(target=make_many_calls) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Total calls should be exactly 100 (not more due to race conditions)
        assert len(limiter.calls) == 100


class TestGlobalLimiters:
    """Test global rate limiter instances."""

    def test_command_limiter_configured(self):
        """Command limiter should be configured with appropriate limits."""
        assert command_limiter.max_calls == 10
        assert command_limiter.period == 60

    def test_query_limiter_configured(self):
        """Query limiter should be configured with appropriate limits."""
        assert query_limiter.max_calls == 100
        assert query_limiter.period == 60

    def test_shell_limiter_configured(self):
        """Shell limiter should be configured with appropriate limits."""
        assert shell_limiter.max_calls == 5
        assert shell_limiter.period == 60


class TestRateLimitIntegration:
    """Test rate limiting integration with tools."""

    @patch("odoo_dev_mcp.tools.terminal.subprocess.run")
    @patch("odoo_dev_mcp.tools.terminal.get_config")
    @patch("odoo_dev_mcp.tools.terminal.audit_log")
    def test_terminal_enforces_rate_limit(self, mock_audit, mock_get_config, mock_run):
        """Terminal tool should enforce rate limiting."""
        from odoo_dev_mcp.tools.terminal import execute_command
        from odoo_dev_mcp.utils.security import command_limiter

        # Reset limiter
        command_limiter.calls = []
        command_limiter.max_calls = 2
        command_limiter.period = 60

        mock_config = Mock()
        mock_config.command.max_timeout = 600
        mock_config.command.working_directory = "/tmp"
        mock_get_config.return_value = mock_config

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # First two should succeed
        execute_command("echo 1")
        execute_command("echo 2")

        # Third should fail with rate limit
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            execute_command("echo 3")

    @patch("odoo_dev_mcp.tools.odoo_shell.subprocess.run")
    @patch("odoo_dev_mcp.tools.odoo_shell.get_config")
    @patch("odoo_dev_mcp.tools.odoo_shell.audit_log")
    def test_shell_enforces_rate_limit(self, mock_audit, mock_get_config, mock_run):
        """Odoo shell tool should enforce rate limiting."""
        from odoo_dev_mcp.tools.odoo_shell import odoo_shell
        from odoo_dev_mcp.utils.security import shell_limiter

        # Reset limiter
        shell_limiter.calls = []
        shell_limiter.max_calls = 1
        shell_limiter.period = 60

        mock_config = Mock()
        mock_config.database.name = "test_db"
        mock_config.odoo.shell_command = "odoo shell"
        mock_config.odoo.config_path = "/etc/odoo/odoo.conf"
        mock_get_config.return_value = mock_config

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # First should succeed
        odoo_shell("print('test')")

        # Second should fail with rate limit
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            odoo_shell("print('test2')")


class TestRateLimiterEdgeCases:
    """Test edge cases in rate limiting."""

    def test_zero_max_calls(self):
        """Limiter with max_calls=0 should reject all."""
        limiter = RateLimiter(max_calls=0, period=60)
        assert limiter.allow() is False

    def test_very_short_period(self):
        """Should handle very short time periods."""
        limiter = RateLimiter(max_calls=1, period=0.001)  # 1ms

        assert limiter.allow() is True
        assert limiter.allow() is False

        time.sleep(0.002)
        assert limiter.allow() is True

    def test_very_long_period(self):
        """Should handle very long time periods."""
        limiter = RateLimiter(max_calls=2, period=3600)  # 1 hour

        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False
