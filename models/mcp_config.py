# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MCPConfig(models.TransientModel):
    """Configuration model for MCP Server settings."""

    _name = 'mcp.config.settings'
    _inherit = 'res.config.settings'
    _description = 'MCP Server Configuration'

    # Server settings
    mcp_server_host = fields.Char(
        string='Server Host',
        default='127.0.0.1',
        config_parameter='mcp.server_host',
        help='Bind address for MCP HTTP server (default: localhost only)'
    )
    mcp_server_port = fields.Integer(
        string='Server Port',
        default=8768,
        config_parameter='mcp.server_port',
        help='Port for MCP HTTP server'
    )
    mcp_api_key = fields.Char(
        string='API Key',
        config_parameter='mcp.api_key',
        help='API key for authenticating MCP client connections (Bearer token)'
    )
    mcp_log_level = fields.Selection(
        [('debug', 'Debug'), ('info', 'Info'), ('warning', 'Warning'), ('error', 'Error')],
        string='Log Level',
        default='info',
        config_parameter='mcp.log_level',
        help='Logging verbosity level'
    )

    # Phone-home settings
    mcp_phone_home_url = fields.Char(
        string='Phone-Home URL',
        config_parameter='mcp.phone_home_url',
        help='API endpoint to register server on startup (leave empty to disable)'
    )
    mcp_heartbeat_interval = fields.Integer(
        string='Heartbeat Interval',
        default=60,
        config_parameter='mcp.heartbeat_interval',
        help='Heartbeat interval in seconds'
    )

    # Command settings
    mcp_command_timeout = fields.Integer(
        string='Default Command Timeout',
        default=30,
        config_parameter='mcp.command_timeout',
        help='Default timeout for command execution in seconds'
    )
    mcp_command_max_timeout = fields.Integer(
        string='Max Command Timeout',
        default=600,
        config_parameter='mcp.command_max_timeout',
        help='Maximum allowed command timeout in seconds'
    )

    # Filesystem settings
    mcp_max_read_size_mb = fields.Integer(
        string='Max Read Size (MB)',
        default=10,
        config_parameter='mcp.max_read_size_mb',
        help='Maximum file size for read operations'
    )
    mcp_max_write_size_mb = fields.Integer(
        string='Max Write Size (MB)',
        default=50,
        config_parameter='mcp.max_write_size_mb',
        help='Maximum file size for write operations'
    )

    # Database settings
    mcp_query_timeout = fields.Integer(
        string='Query Timeout',
        default=30,
        config_parameter='mcp.query_timeout',
        help='Default query timeout in seconds'
    )
    mcp_max_result_rows = fields.Integer(
        string='Max Result Rows',
        default=1000,
        config_parameter='mcp.max_result_rows',
        help='Maximum number of rows returned by queries'
    )

    # Audit logging
    mcp_audit_enabled = fields.Boolean(
        string='Audit Logging Enabled',
        default=True,
        config_parameter='mcp.audit_enabled',
        help='Enable audit logging of all MCP operations'
    )
    mcp_audit_log_path = fields.Char(
        string='Audit Log Path',
        default='/var/log/odoo/mcp_audit.log',
        config_parameter='mcp.audit_log_path',
        help='Path to audit log file'
    )
