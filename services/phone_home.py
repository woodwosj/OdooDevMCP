# -*- coding: utf-8 -*-
"""Phone-home registration mechanism."""

import logging
import socket
from datetime import datetime

import requests

_logger = logging.getLogger(__name__)


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

        # Get network info
        network_info = get_network_info()

        # Get server info
        server_port = int(ICP.get_param('mcp.server_port', default=8768))
        odoo_version = env.registry.version

        # Get server ID (use database name + hostname as unique ID)
        server_id = f"{env.cr.dbname}_{network_info['hostname']}"

        # Build registration payload
        payload = {
            "server_id": server_id,
            "hostname": network_info["hostname"],
            "ip_addresses": {
                "primary": network_info["primary"],
                "all": network_info["all"]
            },
            "port": server_port,
            "transport": "http/sse",
            "version": "1.0.0",
            "odoo_version": odoo_version,
            "database": env.cr.dbname,
            "capabilities": [
                "execute_command",
                "query_database",
                "execute_sql",
                "get_db_schema",
                "read_file",
                "write_file",
                "odoo_shell",
                "service_status",
                "read_config",
                "list_modules",
                "get_module_info",
                "install_module",
                "upgrade_module",
            ],
            "started_at": datetime.utcnow().isoformat() + "Z",
        }

        # Get retry configuration
        retry_count = int(ICP.get_param('mcp.phone_home_retry_count', default=3))
        timeout = int(ICP.get_param('mcp.phone_home_timeout', default=5))

        # Retry logic
        import time
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    phone_home_url,
                    json=payload,
                    timeout=timeout,
                )

                if response.status_code in [200, 201]:
                    _logger.info(
                        f"MCP: Successfully registered server {server_id} at "
                        f"{network_info['primary']}:{server_port}"
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

        # Get network info
        network_info = get_network_info()
        server_id = f"{env.cr.dbname}_{network_info['hostname']}"

        payload = {
            "server_id": server_id,
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Send to /heartbeat endpoint
        heartbeat_url = phone_home_url
        if not heartbeat_url.endswith("/heartbeat"):
            heartbeat_url = heartbeat_url.rstrip("/") + "/heartbeat"

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
