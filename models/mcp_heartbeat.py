# -*- coding: utf-8 -*-
"""MCP Heartbeat cron model."""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MCPHeartbeat(models.AbstractModel):
    _name = 'mcp.heartbeat'
    _description = 'MCP Heartbeat Cron'

    def _cron_send_heartbeat(self):
        """Send heartbeat ping to configured receiver. Called by ir.cron."""
        # Import inside method to avoid circular imports
        import socket
        from ..services.phone_home import send_heartbeat, register_server

        # Check for hostname change before sending heartbeat
        current_hostname = socket.gethostname()
        ICP = self.env['ir.config_parameter'].sudo()
        last_hostname = ICP.get_param('mcp.last_hostname', default='')

        if current_hostname != last_hostname:
            _logger.info(
                f"MCP: Hostname changed from '{last_hostname}' to '{current_hostname}', "
                f"triggering registration before heartbeat"
            )
            # Trigger registration first
            register_server(self.env)
            # Update last_hostname
            ICP.set_param('mcp.last_hostname', current_hostname)

        # Send heartbeat
        result = send_heartbeat(self.env)
        if result:
            _logger.debug("MCP: Heartbeat cron completed successfully")
        return result
