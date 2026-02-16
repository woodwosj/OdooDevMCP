"""Tests for filesystem operations."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest


class TestReadFile:
    """Test file reading operations."""

    @patch("odoo_dev_mcp.tools.filesystem.Path")
    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    @patch("odoo_dev_mcp.tools.filesystem.audit_log")
    def test_reads_text_file(self, mock_audit, mock_validate, mock_get_config, mock_path_cls):
        """Should read text file contents."""
        from odoo_dev_mcp.tools.filesystem import read_file

        mock_config = Mock()
        mock_config.filesystem.max_read_size_mb = 10
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_path.stat.return_value.st_size = 100
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = True
        mock_path.is_symlink.return_value = False
        mock_validate.return_value = mock_path

        content = "test content\nline 2"
        with patch("builtins.open", mock_open(read_data=content)):
            result = read_file("/test/file.txt")

        assert result["content"] == content
        assert result["size_bytes"] == 100
        assert result["encoding"] == "utf-8"
        mock_audit.assert_called_once()

    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    def test_rejects_file_too_large(self, mock_validate, mock_get_config):
        """Should reject files exceeding size limit."""
        from odoo_dev_mcp.tools.filesystem import read_file

        mock_config = Mock()
        mock_config.filesystem.max_read_size_mb = 1  # 1 MB
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_path.stat.return_value.st_size = 2 * 1024 * 1024  # 2 MB
        mock_path.exists.return_value = True
        mock_path.is_file.return_value = True
        mock_validate.return_value = mock_path

        with pytest.raises(ValueError, match="File too large"):
            read_file("/test/large_file.txt")

    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    def test_rejects_nonexistent_file(self, mock_validate, mock_get_config):
        """Should raise error for nonexistent files."""
        from odoo_dev_mcp.tools.filesystem import read_file

        mock_config = Mock()
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_validate.return_value = mock_path

        with pytest.raises(FileNotFoundError):
            read_file("/test/missing.txt")


class TestWriteFile:
    """Test file writing operations."""

    @patch("odoo_dev_mcp.tools.filesystem.Path")
    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    @patch("odoo_dev_mcp.tools.filesystem.audit_log")
    def test_writes_text_file(self, mock_audit, mock_validate, mock_get_config, mock_path_cls):
        """Should write text file contents."""
        from odoo_dev_mcp.tools.filesystem import write_file

        mock_config = Mock()
        mock_config.filesystem.max_write_size_mb = 50
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_validate.return_value = mock_path

        content = "test content"
        with patch("builtins.open", mock_open()) as mock_file:
            result = write_file("/test/file.txt", content)

        assert result["bytes_written"] == len(content)
        assert result["created"] is True
        mock_audit.assert_called_once()

    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    def test_rejects_content_too_large(self, mock_validate, mock_get_config):
        """Should reject content exceeding size limit."""
        from odoo_dev_mcp.tools.filesystem import write_file

        mock_config = Mock()
        mock_config.filesystem.max_write_size_mb = 1  # 1 MB
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_validate.return_value = mock_path

        large_content = "x" * (2 * 1024 * 1024)  # 2 MB

        with pytest.raises(ValueError, match="Content too large"):
            write_file("/test/file.txt", large_content)

    @patch("odoo_dev_mcp.tools.filesystem.Path")
    @patch("odoo_dev_mcp.tools.filesystem.get_config")
    @patch("odoo_dev_mcp.tools.filesystem.validate_path")
    @patch("odoo_dev_mcp.tools.filesystem.audit_log")
    def test_creates_parent_directories(
        self, mock_audit, mock_validate, mock_get_config, mock_path_cls
    ):
        """Should create parent directories when requested."""
        from odoo_dev_mcp.tools.filesystem import write_file

        mock_config = Mock()
        mock_config.filesystem.max_write_size_mb = 50
        mock_get_config.return_value = mock_config

        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path.parent = MagicMock()
        mock_validate.return_value = mock_path

        with patch("builtins.open", mock_open()):
            write_file("/test/subdir/file.txt", "content", create_directories=True)

        mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
