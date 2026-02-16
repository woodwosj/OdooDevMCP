# -*- coding: utf-8 -*-
"""Terminal command execution tool."""

import logging
import subprocess
import time
from typing import Dict, Optional

_logger = logging.getLogger(__name__)


def execute_command(
    env,
    command: str,
    working_directory: Optional[str] = None,
    timeout: int = 30,
    env_vars: Optional[Dict[str, str]] = None,
) -> dict:
    """Execute a shell command on the Odoo server.

    Args:
        env: Odoo environment
        command: The shell command to execute
        working_directory: Working directory for command execution
        timeout: Maximum execution time in seconds (0 = no timeout)
        env_vars: Additional environment variables

    Returns:
        dict: stdout, stderr, exit_code, timed_out, duration_ms
    """
    from ..security.security import audit_log, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'command', max_calls=10, period=60)

    # Get configuration
    ICP = env['ir.config_parameter'].sudo()
    max_timeout = int(ICP.get_param('mcp.command_max_timeout', default=600))

    start_time = time.time()

    # Use configured working directory if not specified
    if working_directory is None:
        working_directory = "/opt/odoo"

    # Validate timeout
    if timeout > max_timeout:
        timeout = max_timeout
    elif timeout == 0:
        timeout = None  # No timeout

    # Build environment
    import os
    exec_env = os.environ.copy()
    if env_vars:
        exec_env.update(env_vars)

    timed_out = False
    exit_code = 0
    stdout_text = ""
    stderr_text = ""

    try:
        result = subprocess.run(
            command,
            shell=True,  # Allowed since this is a trusted local tool
            cwd=working_directory,
            env=exec_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        exit_code = result.returncode
        stdout_text = result.stdout
        stderr_text = result.stderr

    except subprocess.TimeoutExpired as e:
        timed_out = True
        exit_code = -1
        stdout_text = e.stdout.decode("utf-8") if e.stdout else ""
        stderr_text = e.stderr.decode("utf-8") if e.stderr else ""
        _logger.warning(f"Command timed out after {timeout}s: {command[:50]}")

    except Exception as e:
        exit_code = -2
        stderr_text = str(e)
        _logger.error(f"Command execution error: {e}")

    duration_ms = int((time.time() - start_time) * 1000)

    # Audit log
    audit_log(
        env,
        tool="execute_command",
        cmd=command[:100],  # Truncate long commands
        exit_code=exit_code,
        duration_ms=duration_ms,
    )

    return {
        "stdout": stdout_text,
        "stderr": stderr_text,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
    }
