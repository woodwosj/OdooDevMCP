"""Tests for security utilities (validate_path, mask_sensitive_config, audit_log, check_rate_limit)."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from OdooDevMCP.security.security import (
    audit_log,
    check_rate_limit,
    mask_sensitive_config,
    validate_path,
    _rate_limit_state,
)


# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------

class TestValidatePath:
    """Test path validation and symlink resolution."""

    def test_empty_path_raises_error(self):
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_path("")

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            validate_path("/etc/../etc/passwd")

    def test_relative_path_rejected_by_default(self):
        with pytest.raises(ValueError, match="Absolute path required"):
            validate_path("relative/path")

    def test_relative_path_allowed_when_specified(self, tmp_path):
        os.chdir(tmp_path)
        result = validate_path("test.txt", allow_relative=True)
        assert result.is_absolute()

    def test_absolute_path_accepted(self):
        result = validate_path("/tmp/test.txt")
        assert result == Path("/tmp/test.txt")

    def test_symlink_resolution(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("test")

        link = tmp_path / "link.txt"
        link.symlink_to(target)

        result = validate_path(str(link))
        assert result == target.resolve()

    def test_symlink_attack_resolved(self, tmp_path):
        """Symlinks pointing outside allowed paths should be resolved to real path."""
        external_file = Path("/tmp/external_security_test.txt")
        external_file.write_text("sensitive")
        try:
            link = tmp_path / "evil_link.txt"
            link.symlink_to(external_file)

            resolved = validate_path(str(link))
            assert resolved == external_file.resolve()
            assert "evil_link" not in str(resolved)
        finally:
            external_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# mask_sensitive_config
# ---------------------------------------------------------------------------

class TestMaskSensitiveConfig:

    def test_masks_password_fields(self):
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
        config = {"db_password": None, "host": "localhost"}
        masked = mask_sensitive_config(config)
        assert masked["db_password"] is None
        assert masked["host"] == "localhost"

    def test_empty_dict(self):
        assert mask_sensitive_config({}) == {}


# ---------------------------------------------------------------------------
# audit_log
# ---------------------------------------------------------------------------

class TestAuditLog:

    def test_audit_log_writes_entry(self, mock_env):
        """audit_log should write a formatted line to the configured file."""
        audit_log(
            mock_env,
            tool="test_tool",
            duration_ms=100,
            param1="value1",
        )

        log_path = mock_env._icp_store["mcp.audit_log_path"]
        content = Path(log_path).read_text()
        assert "TOOL=test_tool" in content
        assert "DURATION=100ms" in content
        assert "PARAM1=value1" in content
        assert "DB=test_db" in content

    def test_audit_log_creates_directory(self, mock_env):
        """audit_log should create parent directory if missing."""
        nested_path = str(mock_env._tmp_path / "subdir" / "audit.log")
        mock_env._icp_store["mcp.audit_log_path"] = nested_path

        audit_log(mock_env, tool="test")

        assert Path(nested_path).exists()
        assert Path(nested_path).parent.is_dir()

    def test_audit_log_disabled(self, mock_env):
        """When audit is disabled, no file should be written."""
        mock_env._icp_store["mcp.audit_enabled"] = "False"

        audit_log(mock_env, tool="test_disabled")

        log_path = mock_env._icp_store["mcp.audit_log_path"]
        # File should not exist (or be empty if pre-created)
        if Path(log_path).exists():
            assert Path(log_path).read_text() == ""

    def test_audit_log_truncates_long_values(self, mock_env):
        """Values longer than 100 chars should be truncated."""
        long_value = "x" * 200
        audit_log(mock_env, tool="test", data=long_value)

        log_path = mock_env._icp_store["mcp.audit_log_path"]
        content = Path(log_path).read_text()
        # Should contain truncated value (100 chars + "...")
        assert "x" * 100 + "..." in content


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:

    def test_allows_calls_under_limit(self, mock_env):
        for _ in range(5):
            check_rate_limit(mock_env, "test_cat", max_calls=5, period=60)
        # 6th should fail
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            check_rate_limit(mock_env, "test_cat", max_calls=5, period=60)

    def test_different_categories_independent(self, mock_env):
        """Rate limits for different categories should not interfere."""
        check_rate_limit(mock_env, "cat_a", max_calls=1, period=60)
        # cat_b should still work even though cat_a is exhausted
        check_rate_limit(mock_env, "cat_b", max_calls=1, period=60)

    def test_different_databases_independent(self, mock_env):
        """Rate limits should be tracked per database."""
        check_rate_limit(mock_env, "cat", max_calls=1, period=60)

        # Create a second env with different dbname
        from unittest.mock import MagicMock
        env2 = MagicMock()
        env2.cr.dbname = "other_db"
        check_rate_limit(env2, "cat", max_calls=1, period=60)

    def test_sliding_window_expiry(self, mock_env):
        """Old calls should expire outside the time window."""
        # Use very short period
        check_rate_limit(mock_env, "sw", max_calls=1, period=0.05)
        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "sw", max_calls=1, period=0.05)

        time.sleep(0.06)
        # After window expires, should succeed again
        check_rate_limit(mock_env, "sw", max_calls=1, period=0.05)

    def test_zero_max_calls_rejects_all(self, mock_env):
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            check_rate_limit(mock_env, "zero", max_calls=0, period=60)
