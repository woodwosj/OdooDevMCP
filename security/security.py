# -*- coding: utf-8 -*-
"""Security utilities for audit logging, path validation, and rate limiting."""

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_logger = logging.getLogger(__name__)

# In-memory rate limiting state (per-database)
_rate_limit_state = {}


def audit_log(
    env,
    tool: str,
    duration_ms: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """Log tool invocation to audit log.

    Args:
        env: Odoo environment
        tool: Tool name
        duration_ms: Operation duration in milliseconds
        **kwargs: Additional fields to log
    """
    try:
        # Get audit log configuration
        ICP = env['ir.config_parameter'].sudo()
        audit_enabled = ICP.get_param('mcp.audit_enabled', default='True') == 'True'

        if not audit_enabled:
            return

        audit_log_path = ICP.get_param('mcp.audit_log_path', default='/var/log/odoo/mcp_audit.log')

        # Ensure audit log directory exists
        log_dir = Path(audit_log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # Build log entry
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        user_id = env.uid
        database = env.cr.dbname

        parts = [
            f"[{timestamp}]",
            f"DB={database}",
            f"USER={user_id}",
            f"TOOL={tool}"
        ]

        # Add additional fields
        for key, value in kwargs.items():
            # Truncate long values
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            parts.append(f"{key.upper()}={value}")

        if duration_ms is not None:
            parts.append(f"DURATION={duration_ms}ms")

        log_line = " ".join(parts)

        # Write to audit log
        with open(audit_log_path, "a") as f:
            f.write(log_line + "\n")

    except Exception as e:
        _logger.error(f"Failed to write to audit log: {e}")


def validate_path(path: str, allow_relative: bool = False) -> Path:
    """Validate and resolve a file path with symlink resolution.

    Args:
        path: Path to validate
        allow_relative: Allow relative paths

    Returns:
        Resolved absolute Path object with symlinks resolved

    Raises:
        ValueError: If path is invalid or contains path traversal
    """
    if not path:
        raise ValueError("Path cannot be empty")

    path_obj = Path(path)

    # Reject path traversal attempts in the raw path
    if ".." in path_obj.parts:
        raise ValueError("Path traversal not allowed")

    # Convert to absolute and resolve symlinks
    if not path_obj.is_absolute():
        if not allow_relative:
            raise ValueError("Absolute path required")
        path_obj = path_obj.resolve()
    else:
        # Use realpath to resolve symlinks before validation
        path_obj = Path(os.path.realpath(path))

    return path_obj


def mask_sensitive_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive values in configuration dictionary.

    Args:
        config_dict: Configuration dictionary

    Returns:
        Dictionary with sensitive values masked
    """
    sensitive_keys = {
        "db_password",
        "password",
        "admin_passwd",
        "api_key",
        "secret",
        "token",
    }

    masked = {}
    for key, value in config_dict.items():
        if isinstance(value, dict):
            masked[key] = mask_sensitive_config(value)
        elif any(sensitive in key.lower() for sensitive in sensitive_keys):
            masked[key] = "***MASKED***" if value else None
        else:
            masked[key] = value

    return masked


def check_rate_limit(env, category: str, max_calls: int, period: float) -> None:
    """Check if operation is within rate limit.

    Args:
        env: Odoo environment
        category: Rate limit category (command, query, shell, etc.)
        max_calls: Maximum number of calls allowed in the period
        period: Time period in seconds

    Raises:
        RuntimeError: If rate limit exceeded
    """
    # Use database name as key for rate limit state
    db_key = env.cr.dbname

    # Initialize rate limit state for this database if needed
    if db_key not in _rate_limit_state:
        _rate_limit_state[db_key] = {}

    if category not in _rate_limit_state[db_key]:
        _rate_limit_state[db_key][category] = []

    now = time.time()
    calls = _rate_limit_state[db_key][category]

    # Remove old calls outside the period
    calls[:] = [c for c in calls if now - c < period]

    if len(calls) >= max_calls:
        raise RuntimeError(
            f"Rate limit exceeded for {category}: {max_calls} calls per {period} seconds"
        )

    calls.append(now)
