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
        from ..services.phone_home import send_heartbeat
        result = send_heartbeat(self.env)
        if result:
            _logger.debug("MCP: Heartbeat cron completed successfully")
        return result
