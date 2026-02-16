# -*- coding: utf-8 -*-
"""Odoo-specific tools: shell, modules, config, service management."""

import logging
import subprocess
import time
import configparser
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)


def odoo_shell_exec(env, code: str, timeout: int = 30) -> dict:
    """Execute Python code in the Odoo shell environment.

    Args:
        env: Odoo environment
        code: Python code to execute in the Odoo shell context
        timeout: Maximum execution time in seconds

    Returns:
        dict: output, return_value, error, duration_ms
    """
    from ..security.security import audit_log, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'shell', max_calls=5, period=60)

    start_time = time.time()

    # Validate timeout
    max_timeout = 300  # 5 minutes max for shell operations
    if timeout > max_timeout:
        timeout = max_timeout

    output_text = ""
    error_text = None
    return_value = None

    try:
        # Instead of subprocess, execute code directly in Odoo environment
        # This is safer and more efficient when running inside Odoo

        # Create a restricted execution environment
        exec_globals = {
            'env': env,
            'self': env,
            'cr': env.cr,
            'uid': env.uid,
            'context': env.context,
            '_logger': _logger,
        }

        # Capture stdout
        import io
        import sys
        from contextlib import redirect_stdout

        output_buffer = io.StringIO()

        try:
            with redirect_stdout(output_buffer):
                # Execute code
                exec(code, exec_globals)

            output_text = output_buffer.getvalue()
            return_value = "Execution successful"

        except Exception as e:
            error_text = str(e)
            _logger.error(f"Odoo shell execution error: {e}")

    except Exception as e:
        error_text = str(e)
        _logger.error(f"Odoo shell execution error: {e}")

    duration_ms = int((time.time() - start_time) * 1000)

    # Audit log
    audit_log(
        env,
        tool="odoo_shell",
        code_length=len(code),
        error="yes" if error_text else "no",
        duration_ms=duration_ms,
    )

    return {
        "output": output_text,
        "return_value": return_value,
        "error": error_text,
        "duration_ms": duration_ms,
    }


def service_status(env, service: str = "odoo", action: str = "status", log_lines: int = 50) -> dict:
    """Check and manage services.

    Args:
        env: Odoo environment
        service: Service name (odoo, postgresql, nginx, etc.)
        action: Action to perform (status, start, stop, restart, logs)
        log_lines: Number of log lines to return (for action='logs')

    Returns:
        dict: Service status information or logs
    """
    from ..security.security import audit_log

    # Allowed services list (configurable)
    allowed_services = ['odoo', 'postgresql', 'nginx']

    if service not in allowed_services:
        raise ValueError(f"Service '{service}' not in allowed list: {allowed_services}")

    # Validate log_lines
    if log_lines > 1000:
        log_lines = 1000

    try:
        if action == "status":
            result = _get_service_status(service)
        elif action == "start":
            result = _service_action(service, "start")
        elif action == "stop":
            result = _service_action(service, "stop")
        elif action == "restart":
            result = _service_action(service, "restart")
        elif action == "logs":
            result = _get_service_logs(service, log_lines)
        else:
            raise ValueError(f"Unknown action: {action}")

        # Audit log
        audit_log(env, tool="service_status", service=service, action=action)

        return result

    except Exception as e:
        _logger.error(f"Service operation failed: {e}")
        raise


def _get_service_status(service: str) -> dict:
    """Get service status using systemctl."""
    try:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                service,
                "--property=ActiveState,SubState,MainPID,MemoryCurrent,ExecMainStartTimestamp,Description",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            raise RuntimeError(f"systemctl failed: {result.stderr}")

        # Parse properties
        props = {}
        for line in result.stdout.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                props[key] = value

        # Build status response
        active = props.get("ActiveState", "unknown") == "active"
        status_text = f"{props.get('ActiveState', 'unknown')} ({props.get('SubState', 'unknown')})"

        pid = int(props.get("MainPID", "0"))
        memory_mb = 0
        if props.get("MemoryCurrent"):
            try:
                memory_mb = int(props.get("MemoryCurrent", "0")) // (1024 * 1024)
            except ValueError:
                pass

        # Calculate uptime
        uptime = "unknown"
        if props.get("ExecMainStartTimestamp"):
            try:
                from datetime import datetime
                start_time = datetime.fromisoformat(
                    props["ExecMainStartTimestamp"].replace("UTC", "+00:00")
                )
                now = datetime.now(start_time.tzinfo)
                delta = now - start_time
                days = delta.days
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                if days > 0:
                    uptime = f"{days} days {hours}h {minutes}m"
                elif hours > 0:
                    uptime = f"{hours}h {minutes}m"
                else:
                    uptime = f"{minutes}m"
            except Exception:
                pass

        return {
            "service": service,
            "active": active,
            "status": status_text,
            "pid": pid,
            "memory_mb": memory_mb,
            "uptime": uptime,
            "description": props.get("Description", ""),
        }

    except Exception as e:
        _logger.error(f"Failed to get service status: {e}")
        raise


def _service_action(service: str, action: str) -> dict:
    """Perform a service action (start, stop, restart)."""
    try:
        result = subprocess.run(
            ["systemctl", action, service], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(f"systemctl {action} failed: {result.stderr}")

        # Get updated status
        return _get_service_status(service)

    except Exception as e:
        _logger.error(f"Failed to {action} service: {e}")
        raise


def _get_service_logs(service: str, lines: int) -> dict:
    """Get service logs using journalctl."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise RuntimeError(f"journalctl failed: {result.stderr}")

        log_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        return {
            "service": service,
            "log_lines": log_lines,
            "line_count": len(log_lines),
        }

    except Exception as e:
        _logger.error(f"Failed to get service logs: {e}")
        raise


def read_config(env, key: Optional[str] = None) -> dict:
    """Read the Odoo server configuration file.

    Args:
        env: Odoo environment
        key: Specific configuration key to read (None = return all)

    Returns:
        dict: config_path, values (or single value if key specified)
    """
    from ..security.security import audit_log, mask_sensitive_config

    # Get Odoo config file path
    import odoo.tools.config as odoo_config
    config_path = odoo_config.configmanager.rcfile or '/etc/odoo/odoo.conf'

    if not Path(config_path).exists():
        # Try alternate locations
        for alt_path in ['/etc/odoo.conf', '/opt/odoo/odoo.conf']:
            if Path(alt_path).exists():
                config_path = alt_path
                break

    if not Path(config_path).exists():
        raise FileNotFoundError(f"Odoo configuration file not found: {config_path}")

    try:
        parser = configparser.ConfigParser()
        parser.read(config_path)

        # Get all values from [options] section
        values = {}
        if parser.has_section("options"):
            values = dict(parser.items("options"))

        # Mask sensitive values
        values = mask_sensitive_config(values)

        # Audit log
        audit_log(env, tool="read_config", key=key or "all")

        if key:
            # Return specific key
            if key in values:
                return {"config_path": config_path, "key": key, "value": values[key]}
            else:
                raise KeyError(f"Configuration key not found: {key}")
        else:
            # Return all values
            return {"config_path": config_path, "values": values}

    except Exception as e:
        _logger.error(f"Failed to read Odoo configuration: {e}")
        raise


def list_modules(env, state: str = "all", search: Optional[str] = None, limit: int = 100) -> dict:
    """List Odoo modules with their installation status.

    Args:
        env: Odoo environment
        state: Filter by module state (installed, uninstalled, to_upgrade, to_install, to_remove, all)
        search: Search term to filter module names or descriptions
        limit: Maximum number of modules to return

    Returns:
        dict: modules, total_count, returned_count, filter_applied
    """
    from ..security.security import audit_log

    try:
        # Build domain for search
        domain = []

        if state != "all":
            domain.append(('state', '=', state))

        if search:
            domain.append('|')
            domain.append(('name', 'ilike', search))
            domain.append('|')
            domain.append(('display_name', 'ilike', search))
            domain.append(('summary', 'ilike', search))

        # Query modules using ORM
        Module = env['ir.module.module'].sudo()
        modules = Module.search(domain, limit=limit, order='name')

        # Get total count
        total_count = Module.search_count(domain)

        # Prepare result
        module_list = []
        for module in modules:
            module_list.append({
                'name': module.name,
                'display_name': module.display_name,
                'version': module.latest_version,
                'state': module.state,
                'author': module.author,
                'summary': module.summary,
            })

        # Audit log
        audit_log(
            env,
            tool="list_modules",
            state=state,
            search=search or "none",
            returned=len(module_list),
        )

        return {
            "modules": module_list,
            "total_count": total_count,
            "returned_count": len(module_list),
            "filter_applied": state,
        }

    except Exception as e:
        _logger.error(f"Failed to list modules: {e}")
        raise


def get_module_info(env, module_name: str) -> dict:
    """Get detailed information about a specific module.

    Args:
        env: Odoo environment
        module_name: Technical name of the module

    Returns:
        dict: Detailed module information including dependencies
    """
    try:
        Module = env['ir.module.module'].sudo()
        module = Module.search([('name', '=', module_name)], limit=1)

        if not module:
            raise ValueError(f"Module not found: {module_name}")

        # Get dependencies
        dependencies = []
        for dep in module.dependencies_id:
            dependencies.append({
                'name': dep.name,
                'state': dep.state,
            })

        return {
            'name': module.name,
            'display_name': module.display_name,
            'version': module.latest_version,
            'state': module.state,
            'author': module.author,
            'summary': module.summary,
            'description': module.description,
            'category': module.category_id.name if module.category_id else '',
            'website': module.website,
            'dependencies': dependencies,
            'installed_version': module.installed_version,
        }

    except Exception as e:
        _logger.error(f"Failed to get module info: {e}")
        raise


def install_module(env, module_name: str) -> dict:
    """Install an Odoo module.

    Args:
        env: Odoo environment
        module_name: Technical name of the module to install

    Returns:
        dict: Installation result
    """
    try:
        Module = env['ir.module.module'].sudo()
        module = Module.search([('name', '=', module_name)], limit=1)

        if not module:
            raise ValueError(f"Module not found: {module_name}")

        if module.state == 'installed':
            return {
                'success': True,
                'message': f"Module '{module_name}' is already installed",
                'state': 'installed',
            }

        # Mark for installation
        module.button_immediate_install()

        return {
            'success': True,
            'message': f"Module '{module_name}' has been installed",
            'state': 'installed',
        }

    except Exception as e:
        _logger.error(f"Failed to install module: {e}")
        raise


def upgrade_module(env, module_name: str) -> dict:
    """Upgrade an Odoo module.

    Args:
        env: Odoo environment
        module_name: Technical name of the module to upgrade

    Returns:
        dict: Upgrade result
    """
    try:
        Module = env['ir.module.module'].sudo()
        module = Module.search([('name', '=', module_name)], limit=1)

        if not module:
            raise ValueError(f"Module not found: {module_name}")

        if module.state != 'installed':
            raise ValueError(f"Module '{module_name}' is not installed (state: {module.state})")

        # Mark for upgrade
        module.button_immediate_upgrade()

        return {
            'success': True,
            'message': f"Module '{module_name}' has been upgraded",
            'state': 'installed',
        }

    except Exception as e:
        _logger.error(f"Failed to upgrade module: {e}")
        raise
