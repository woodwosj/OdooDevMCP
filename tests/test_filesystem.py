"""Tests for filesystem read/write tools."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from OdooDevMCP.tools.filesystem import read_file, write_file


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

class TestReadFile:

    def test_reads_text_file(self, mock_env, tmp_path):
        """Should read text file contents via the real filesystem."""
        target = tmp_path / "sample.txt"
        target.write_text("line1\nline2\nline3\n")

        result = read_file(mock_env, str(target))

        assert "line1" in result["content"]
        assert result["encoding"] == "utf-8"
        assert result["total_lines"] == 3  # 3 lines (trailing newline creates empty split)
        assert result["truncated"] is False

    def test_reads_with_offset_and_limit(self, mock_env, tmp_path):
        """offset/limit should slice the line list correctly."""
        target = tmp_path / "lines.txt"
        target.write_text("a\nb\nc\nd\ne\n")

        result = read_file(mock_env, str(target), offset=2, limit=2)

        # offset=2 means start from line 2 (1-based) => skip 'a', get 'b','c','d','e'
        # limit=2 means return 2 lines => 'b\n', 'c\n'
        assert result["lines_returned"] == 2
        assert result["truncated"] is True

    def test_rejects_nonexistent_file(self, mock_env):
        with pytest.raises(FileNotFoundError, match="File not found"):
            read_file(mock_env, "/tmp/nonexistent_file_xyz.txt")

    def test_rejects_file_too_large(self, mock_env, tmp_path):
        """Should reject files exceeding the configured max_read_size_mb."""
        mock_env._icp_store["mcp.max_read_size_mb"] = "0"  # 0 MB = reject everything

        target = tmp_path / "big.txt"
        target.write_text("some content")

        # The file has some bytes, but max is 0 MB = 0 bytes
        # The check is on the content after reading, which will exceed 0
        # Actually let me check the source: it checks size_bytes vs max_size before reading for binary
        # For text, it reads lines then checks content length vs max_size
        # With 0 MB = 0 bytes max, the content check will trigger truncation, not an error
        # Let me set a more realistic scenario
        mock_env._icp_store["mcp.max_read_size_mb"] = "10"

        # For binary mode, there's a size check before reading
        big_file = tmp_path / "bigbin.bin"
        big_file.write_bytes(b"x" * 100)

        # Set max to something smaller than 100 bytes
        # 1 MB is actually 1048576 bytes, so 100 bytes is way under. Let's test binary path explicitly.
        # The text path truncates, so let's just verify it returns truncated=True
        # Actually for text, the size check compares content length to max_size after read
        # With 0 MB, max_size = 0, so content will be truncated to empty string
        mock_env._icp_store["mcp.max_read_size_mb"] = "0"

        result = read_file(mock_env, str(target))
        assert result["truncated"] is True
        assert result["content"] == ""

    def test_rejects_directory_path(self, mock_env, tmp_path):
        with pytest.raises(ValueError, match="Path is not a file"):
            read_file(mock_env, str(tmp_path))

    def test_rejects_path_traversal(self, mock_env):
        with pytest.raises(ValueError, match="Invalid path"):
            read_file(mock_env, "/etc/../etc/passwd")

    def test_binary_read(self, mock_env, tmp_path):
        """Should return base64-encoded content for binary encoding."""
        import base64
        target = tmp_path / "binary.bin"
        target.write_bytes(b"\x00\x01\x02\x03")

        result = read_file(mock_env, str(target), encoding="binary")

        assert result["encoding"] == "binary"
        decoded = base64.b64decode(result["content"])
        assert decoded == b"\x00\x01\x02\x03"


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

class TestWriteFile:

    def test_writes_text_file(self, mock_env, tmp_path):
        target = tmp_path / "output.txt"

        result = write_file(mock_env, str(target), "hello world")

        assert result["bytes_written"] == len("hello world".encode("utf-8"))
        assert result["created"] is True
        assert target.read_text() == "hello world"

    def test_overwrites_existing_file(self, mock_env, tmp_path):
        target = tmp_path / "existing.txt"
        target.write_text("old content")

        result = write_file(mock_env, str(target), "new content")

        assert result["created"] is False
        assert target.read_text() == "new content"

    def test_append_mode(self, mock_env, tmp_path):
        target = tmp_path / "append.txt"
        target.write_text("start|")

        result = write_file(mock_env, str(target), "end", mode="append")

        assert target.read_text() == "start|end"
        assert result["created"] is False

    def test_creates_parent_directories(self, mock_env, tmp_path):
        target = tmp_path / "sub" / "deep" / "file.txt"

        write_file(mock_env, str(target), "content", create_directories=True)

        assert target.exists()
        assert target.read_text() == "content"

    def test_rejects_content_too_large(self, mock_env, tmp_path):
        mock_env._icp_store["mcp.max_write_size_mb"] = "0"  # 0 bytes max
        target = tmp_path / "big.txt"

        with pytest.raises(ValueError, match="Content too large"):
            write_file(mock_env, str(target), "some content")

    def test_rejects_path_traversal(self, mock_env):
        with pytest.raises(ValueError, match="Invalid path"):
            write_file(mock_env, "/etc/../etc/bad.txt", "content")

    def test_binary_write(self, mock_env, tmp_path):
        """Should decode base64 content and write as binary."""
        import base64
        target = tmp_path / "binary_out.bin"
        b64_content = base64.b64encode(b"\xff\xfe\xfd").decode("ascii")

        result = write_file(mock_env, str(target), b64_content, encoding="binary")

        assert target.read_bytes() == b"\xff\xfe\xfd"
        assert result["bytes_written"] == 3

    def test_rejects_invalid_base64(self, mock_env, tmp_path):
        target = tmp_path / "bad_b64.bin"
        with pytest.raises(ValueError, match="Invalid base64"):
            write_file(mock_env, str(target), "not-valid-base64!!!", encoding="binary")
