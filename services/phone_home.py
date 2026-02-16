# -*- coding: utf-8 -*-
"""Phone-home registration mechanism."""

import logging
import os
import socket
import time
from datetime import datetime, timezone

import requests
from odoo import release

_logger = logging.getLogger(__name__)

# Module-level timestamp for uptime calculation
_server_start_time = time.time()


def get_server_hostname() -> str:
    """Get current server hostname.

    Returns:
        str: Current hostname from socket.gethostname()
    """
    return socket.gethostname()


def get_network_info() -> dict:
    """Get hostname and IP addresses."""
    hostname = socket.gethostname()

    # Get all IP addresses
    ip_addresses = []
    try:
        # Get primary IP (the one that would connect to internet)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        ip_addresses.append(primary_ip)
    except Exception:
        primary_ip = "127.0.0.1"

    # Get all addresses
    try:
        all_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in all_ips:
            if ip not in ip_addresses:
                ip_addresses.append(ip)
    except Exception:
        pass

    return {
        "hostname": hostname,
        "primary": primary_ip,
        "all": ip_addresses
    }


def _build_server_payload(env) -> dict:
    """Build common server payload fields for registration and heartbeat.

    Args:
        env: Odoo environment

    Returns:
        dict: Payload containing server_id, hostname, ip_addresses, port,
              transport, version, odoo_version, database, capabilities, odoo_stage
    """
    # Import tool registry to get dynamic capabilities
    from ..tools.registry import get_tool_registry

    # Get configuration
    ICP = env['ir.config_parameter'].sudo()
    server_port = int(ICP.get_param('mcp.server_port', default=8768))

    # Get network info
    network_info = get_network_info()

    # Get server ID (use database name + hostname as unique ID)
    server_id = f"{env.cr.dbname}_{network_info['hostname']}"

    # Get odoo_stage from environment variable (Odoo.sh sets this)
    odoo_stage = os.environ.get('ODOO_STAGE', '')

    return {
        "server_id": server_id,
        "hostname": network_info["hostname"],
        "ip_addresses": {
            "primary": network_info["primary"],
            "all": network_info["all"]
        },
        "port": server_port,
        "transport": "http/sse",
        "version": "1.0.0",
        "odoo_version": release.version,
        "database": env.cr.dbname,
        "capabilities": list(get_tool_registry().keys()),
        "odoo_stage": odoo_stage,
    }


def register_server(env) -> bool:
    """Register server with phone-home endpoint.

    Args:
        env: Odoo environment

    Returns:
        bool: True if registration successful, False otherwise
    """
    try:
        # Get configuration
        ICP = env['ir.config_parameter'].sudo()
        phone_home_url = ICP.get_param('mcp.phone_home_url', default=False)

        if not phone_home_url:
            _logger.info("MCP: Phone-home disabled (no URL configured)")
            return False

        # Build registration payload from shared helper
        payload = _build_server_payload(env)
        payload["started_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Get retry configuration
        retry_count = int(ICP.get_param('mcp.phone_home_retry_count', default=3))
        timeout = int(ICP.get_param('mcp.phone_home_timeout', default=5))

        # Retry logic
        for attempt in range(retry_count):
            try:
                register_url = phone_home_url.rstrip('/') + '/register'
                response = requests.post(
                    register_url,
                    json=payload,
                    timeout=timeout,
                )

                if response.status_code in [200, 201]:
                    _logger.info(
                        f"MCP: Successfully registered server {payload['server_id']} at "
                        f"{payload['ip_addresses']['primary']}:{payload['port']}"
                    )
                    return True
                else:
                    _logger.warning(
                        f"MCP: Phone-home registration failed: HTTP {response.status_code}"
                    )

            except Exception as e:
                _logger.warning(f"MCP: Phone-home registration attempt {attempt + 1} failed: {e}")

            # Exponential backoff
            if attempt < retry_count - 1:
                backoff = 2 ** attempt
                time.sleep(backoff)

        _logger.error("MCP: Phone-home registration failed after all retries")
        return False

    except Exception as e:
        _logger.error(f"MCP: Error in register_server: {e}", exc_info=True)
        return False


def send_heartbeat(env) -> bool:
    """Send heartbeat ping to phone-home endpoint.

    Args:
        env: Odoo environment

    Returns:
        bool: True if heartbeat successful, False otherwise
    """
    try:
        # Get configuration
        ICP = env['ir.config_parameter'].sudo()
        phone_home_url = ICP.get_param('mcp.phone_home_url', default=False)

        if not phone_home_url:
            return False

        # Build enriched heartbeat payload from shared helper
        payload = _build_server_payload(env)

        # Add heartbeat-specific fields
        payload["status"] = "healthy"
        payload["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload["uptime_seconds"] = time.time() - _server_start_time

        # Send to /heartbeat endpoint
        heartbeat_url = phone_home_url.rstrip('/') + '/heartbeat'

        timeout = int(ICP.get_param('mcp.phone_home_timeout', default=5))

        response = requests.post(
            heartbeat_url,
            json=payload,
            timeout=timeout
        )

        if response.status_code in [200, 201]:
            _logger.debug("MCP: Heartbeat sent successfully")
            return True
        else:
            _logger.warning(f"MCP: Heartbeat failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        _logger.warning(f"MCP: Heartbeat failed: {e}")
        return False
