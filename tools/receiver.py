# -*- coding: utf-8 -*-
"""Receiver registration tool for phone-home notifications."""

import logging
import socket
from typing import Optional

_logger = logging.getLogger(__name__)


def register_receiver(env, receiver_url: str) -> dict:
    """Register a receiver URL for phone-home notifications and heartbeats.

    Args:
        env: Odoo environment
        receiver_url: Base URL of the receiver server (e.g., https://abc123.ngrok.io)

    Returns:
        dict: success, server_id, url_stored, heartbeat_schedule
    """
    from ..security.security import audit_log, check_rate_limit

    # Rate limit
    check_rate_limit(env, 'register_receiver', max_calls=5, period=60)

    # Validate URL
    if not receiver_url or not isinstance(receiver_url, str):
        raise ValueError("receiver_url is required and must be a non-empty string")

    receiver_url = receiver_url.strip()
    if not receiver_url.startswith(('http://', 'https://')):
        raise ValueError("receiver_url must start with http:// or https://")

    # Normalize: strip /register suffix and trailing slash
    base_url = receiver_url
    if base_url.endswith('/register'):
        base_url = base_url[:-len('/register')]
    base_url = base_url.rstrip('/')

    if not base_url:
        raise ValueError("receiver_url resolves to an empty base URL after normalization")

    try:
        # Store base URL in config
        ICP = env['ir.config_parameter'].sudo()
        ICP.set_param('mcp.phone_home_url', base_url)

        # Immediately register with the receiver
        from ..services.phone_home import register_server, get_network_info
        registration_success = register_server(env)

        # Build server_id (same logic as phone_home.py)
        network_info = get_network_info()
        server_id = f"{env.cr.dbname}_{network_info['hostname']}"

        # Audit log
        audit_log(env, tool='register_receiver', receiver_url=base_url)

        return {
            "success": True,
            "server_id": server_id,
            "url_stored": base_url,
            "registration_sent": registration_success,
            "heartbeat_schedule": "every 1 minute via cron",
        }

    except Exception as e:
        _logger.error(f"Error in register_receiver: {e}")
        raise
