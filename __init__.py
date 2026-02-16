# -*- coding: utf-8 -*-

from . import models
from . import controllers
from . import tools
from . import services

import logging
from .services.phone_home import register_server

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-installation hook to register server with phone-home endpoint."""
    _logger.info("OdooDevMCP: Running post-install hook")

    try:
        # Get configuration from ir.config_parameter
        ICP = env['ir.config_parameter'].sudo()
        phone_home_url = ICP.get_param('mcp.phone_home_url', default=False)

        if phone_home_url:
            _logger.info(f"OdooDevMCP: Phone-home URL configured: {phone_home_url}")
            # Register server asynchronously
            success = register_server(env)
            if success:
                _logger.info("OdooDevMCP: Successfully registered with phone-home endpoint")
            else:
                _logger.warning("OdooDevMCP: Failed to register with phone-home endpoint")
        else:
            _logger.info("OdooDevMCP: Phone-home disabled (no URL configured)")

    except Exception as e:
        _logger.error(f"OdooDevMCP: Error in post_init_hook: {e}")
