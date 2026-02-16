# -*- coding: utf-8 -*-
"""Filesystem read/write tools."""

import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


def read_file(
    env,
    path: str,
    encoding: str = "utf-8",
    offset: int = 0,
    limit: int = 0
) -> dict:
    """Read the contents of a file from the Odoo server filesystem.

    Args:
        env: Odoo environment
        path: Absolute path to the file to read
        encoding: Text encoding ('utf-8', 'binary', etc.)
        offset: Line number to start reading from (1-based, 0 = start)
        limit: Maximum number of lines to return (0 = entire file)

    Returns:
        dict: path, content, size_bytes, lines_returned, total_lines, truncated, encoding
    """
    from ..security.security import audit_log, validate_path, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'file_read', max_calls=50, period=60)

    # Get configuration
    ICP = env['ir.config_parameter'].sudo()
    max_read_size_mb = int(ICP.get_param('mcp.max_read_size_mb', default=10))

    # Validate path
    try:
        file_path = validate_path(path, allow_relative=False)
    except ValueError as e:
        raise ValueError(f"Invalid path: {e}")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    # Check file size
    size_bytes = file_path.stat().st_size
    max_size = max_read_size_mb * 1024 * 1024

    # Handle binary encoding
    if encoding == "binary":
        if size_bytes > max_size:
            raise ValueError(
                f"File too large for binary read: {size_bytes} bytes "
                f"(max {max_read_size_mb}MB)"
            )

        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")

        audit_log(env, tool="read_file", path=path, size_bytes=size_bytes, encoding="binary")

        return {
            "path": str(file_path),
            "content": content,
            "size_bytes": size_bytes,
            "lines_returned": 0,
            "total_lines": 0,
            "truncated": False,
            "encoding": "binary",
        }

    # Text file handling
    try:
        with open(file_path, "r", encoding=encoding) as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        raise ValueError(f"File encoding error. Try encoding='binary' for binary files.")

    total_lines = len(lines)

    # Apply offset and limit
    if offset > 0:
        lines = lines[offset - 1:]

    truncated = False
    if limit > 0 and len(lines) > limit:
        lines = lines[:limit]
        truncated = True

    # Check if content would be too large
    content = "".join(lines)
    if len(content) > max_size:
        # Truncate content
        content = content[:max_size]
        truncated = True

    lines_returned = len(lines)

    audit_log(
        env,
        tool="read_file",
        path=path,
        size_bytes=size_bytes,
        lines=lines_returned,
        encoding=encoding,
    )

    return {
        "path": str(file_path),
        "content": content,
        "size_bytes": size_bytes,
        "lines_returned": lines_returned,
        "total_lines": total_lines,
        "truncated": truncated,
        "encoding": encoding,
    }


def write_file(
    env,
    path: str,
    content: str,
    encoding: str = "utf-8",
    mode: str = "overwrite",
    create_directories: bool = True,
) -> dict:
    """Write content to a file on the Odoo server filesystem.

    Args:
        env: Odoo environment
        path: Absolute path to the file to write
        content: Content to write
        encoding: Text encoding ('utf-8', 'binary' for base64 content)
        mode: Write mode ('overwrite' or 'append')
        create_directories: Create parent directories if they don't exist

    Returns:
        dict: path, bytes_written, created
    """
    from ..security.security import audit_log, validate_path, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'file_write', max_calls=30, period=60)

    # Get configuration
    ICP = env['ir.config_parameter'].sudo()
    max_write_size_mb = int(ICP.get_param('mcp.max_write_size_mb', default=50))

    # Validate path
    try:
        file_path = validate_path(path, allow_relative=False)
    except ValueError as e:
        raise ValueError(f"Invalid path: {e}")

    # Check if file exists
    file_exists = file_path.exists()
    created = not file_exists

    # Create parent directories if needed
    if create_directories and not file_path.parent.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle binary encoding
    if encoding == "binary":
        try:
            binary_content = base64.b64decode(content)
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {e}")

        # Check size
        max_size = max_write_size_mb * 1024 * 1024
        if len(binary_content) > max_size:
            raise ValueError(
                f"Content too large: {len(binary_content)} bytes "
                f"(max {max_write_size_mb}MB)"
            )

        # Atomic write via temp file
        temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent)
        try:
            os.write(temp_fd, binary_content)
            os.close(temp_fd)
            os.replace(temp_path, file_path)
        except Exception:
            os.close(temp_fd)
            if Path(temp_path).exists():
                os.unlink(temp_path)
            raise

        bytes_written = len(binary_content)

    else:
        # Text file handling
        content_bytes = content.encode(encoding)

        # Check size
        max_size = max_write_size_mb * 1024 * 1024
        if len(content_bytes) > max_size:
            raise ValueError(
                f"Content too large: {len(content_bytes)} bytes "
                f"(max {max_write_size_mb}MB)"
            )

        if mode == "append" and file_exists:
            # Append mode
            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)
            bytes_written = len(content_bytes)
        else:
            # Overwrite mode - atomic write via temp file
            temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent, text=True)
            try:
                os.write(temp_fd, content_bytes)
                os.close(temp_fd)
                os.replace(temp_path, file_path)
            except Exception:
                os.close(temp_fd)
                if Path(temp_path).exists():
                    os.unlink(temp_path)
                raise

            bytes_written = len(content_bytes)

    audit_log(
        env,
        tool="write_file",
        path=path,
        bytes=bytes_written,
        mode=mode,
        created=created,
    )

    return {
        "path": str(file_path),
        "bytes_written": bytes_written,
        "created": created,
    }
