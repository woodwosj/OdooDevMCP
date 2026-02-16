"""Tests for security utilities."""

import os
import time
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from odoo_dev_mcp.utils.security import (
    RateLimiter,
    audit_log,
    command_limiter,
    mask_sensitive_config,
    validate_path,
)


class TestValidatePath:
    """Test path validation and symlink resolution."""

    def test_empty_path_raises_error(self):
        """Empty path should raise ValueError."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_path("")

    def test_path_traversal_rejected(self):
        """Paths with .. should be rejected."""
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            validate_path("/etc/../etc/passwd")

    def test_relative_path_rejected_by_default(self):
        """Relative paths should be rejected by default."""
        with pytest.raises(ValueError, match="Absolute path required"):
            validate_path("relative/path")

    def test_relative_path_allowed_when_specified(self, tmp_path):
        """Relative paths should be allowed when flag is set."""
        os.chdir(tmp_path)
        result = validate_path("test.txt", allow_relative=True)
        assert result.is_absolute()

    def test_absolute_path_accepted(self):
        """Absolute paths should be accepted."""
        result = validate_path("/tmp/test.txt")
        assert result == Path("/tmp/test.txt")

    def test_symlink_resolution(self, tmp_path):
        """Symlinks should be resolved using realpath."""
        # Create a real file
        target = tmp_path / "target.txt"
        target.write_text("test")

        # Create a symlink
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        # Validate the symlink - should resolve to target
        result = validate_path(str(link))
        assert result == target.resolve()


class TestMaskSensitiveConfig:
    """Test configuration masking."""

    def test_masks_password_fields(self):
        """Password fields should be masked."""
        config = {
            "db_password": "secret123",
            "admin_passwd": "admin123",
            "api_key": "key123",
            "normal_field": "visible",
        }

        masked = mask_sensitive_config(config)

        assert masked["db_password"] == "***MASKED***"
        assert masked["admin_passwd"] == "***MASKED***"
        assert masked["api_key"] == "***MASKED***"
        assert masked["normal_field"] == "visible"

    def test_masks_nested_config(self):
        """Nested password fields should be masked."""
        config = {
            "database": {"password": "secret", "host": "localhost"},
            "server": {"token": "abc123", "port": 8080},
        }

        masked = mask_sensitive_config(config)

        assert masked["database"]["password"] == "***MASKED***"
        assert masked["database"]["host"] == "localhost"
        assert masked["server"]["token"] == "***MASKED***"
        assert masked["server"]["port"] == 8080

    def test_null_passwords_remain_null(self):
        """Null password values should stay null, not masked."""
        config = {"db_password": None, "host": "localhost"}

        masked = mask_sensitive_config(config)

        assert masked["db_password"] is None
        assert masked["host"] == "localhost"


class TestAuditLog:
    """Test audit logging functionality."""

    def test_audit_log_writes_entry(self, temp_audit_log, mock_config):
        """Audit log should write formatted entries."""
        with patch("odoo_dev_mcp.utils.security.get_config", return_value=mock_config):
            mock_config.logging.audit_log = temp_audit_log

            audit_log(
                tool="test_tool",
                client="test_client",
                duration_ms=100,
                param1="value1",
                param2="value2",
            )

            with open(temp_audit_log, "r") as f:
                content = f.read()

            assert "TOOL=test_tool" in content
            assert "CLIENT=test_client" in content
            assert "DURATION=100ms" in content
            assert "PARAM1=value1" in content
            assert "PARAM2=value2" in content

    def test_audit_log_creates_directory(self, tmp_path, mock_config):
        """Audit log should create parent directory if missing."""
        log_path = tmp_path / "subdir" / "audit.log"

        with patch("odoo_dev_mcp.utils.security.get_config", return_value=mock_config):
            mock_config.logging.audit_log = str(log_path)

            audit_log(tool="test", client="client")

            assert log_path.exists()
            assert log_path.parent.is_dir()


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_allows_calls_under_limit(self):
        """Rate limiter should allow calls under the limit."""
        limiter = RateLimiter(max_calls=5, period=60)

        # Should allow first 5 calls
        for _ in range(5):
            assert limiter.allow() is True

        # Should reject 6th call
        assert limiter.allow() is False

    def test_resets_after_period(self):
        """Rate limiter should reset after the time period."""
        limiter = RateLimiter(max_calls=2, period=0.1)  # 100ms period

        # Use up the limit
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False

        # Wait for period to expire
        time.sleep(0.15)

        # Should allow again
        assert limiter.allow() is True

    def test_thread_safety(self):
        """Rate limiter should be thread-safe."""
        import threading

        limiter = RateLimiter(max_calls=10, period=60)
        results = []

        def make_call():
            results.append(limiter.allow())

        threads = [threading.Thread(target=make_call) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 10 True results and 10 False
        assert results.count(True) == 10
        assert results.count(False) == 10

    def test_global_command_limiter_exists(self):
        """Global command limiter should be initialized."""
        assert command_limiter is not None
        assert command_limiter.max_calls == 10
        assert command_limiter.period == 60


class TestC3SymlinkFix:
    """Test that C3 symlink vulnerability is fixed."""

    def test_symlink_attack_prevented(self, tmp_path):
        """Symlinks pointing outside allowed paths should be resolved."""
        # Create a file outside the tmp directory
        external_file = Path("/tmp/external_file.txt")
        external_file.write_text("sensitive")

        # Create a symlink in tmp pointing to external file
        link = tmp_path / "evil_link.txt"
        link.symlink_to(external_file)

        # Validate should resolve the symlink
        resolved = validate_path(str(link))

        # Should resolve to the real path, not the link
        assert resolved == external_file.resolve()
        assert "evil_link" not in str(resolved)

        # Cleanup
        external_file.unlink()
