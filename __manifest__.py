# -*- coding: utf-8 -*-
{
    'name': 'Odoo Dev MCP Server',
    'version': '1.0.0',
    'category': 'Tools',
    'summary': 'MCP Server for Odoo Development and Administration',
    'description': """
Odoo Dev MCP Server
===================

This module provides a Model Context Protocol (MCP) server that runs within Odoo,
giving AI development agents access to:

* Terminal command execution
* Direct PostgreSQL database access
* File system operations
* Odoo shell execution
* Service management
* Module management

The server exposes an HTTP endpoint at /mcp/v1 for MCP client connections.

On module installation, it phones home to a configured API endpoint with
hostname and network address for fleet discovery.

Features:
---------
* Full Odoo ORM access via shell execution
* Direct database queries using Odoo's cursor
* File read/write operations
* System service status and management
* Module listing and inspection
* Audit logging of all operations
* Rate limiting for security
* Path validation and security controls

Security:
---------
This is a DEVELOPMENT and ADMINISTRATION tool. Access should be restricted
to authorized MCP clients only via Odoo API keys (auth='bearer').
All operations are logged to the audit log.

Requirements:
-------------
* Odoo 19.0
* Python 3.10+
* psycopg2
    """,
    'author': 'Odoo Dev MCP Team',
    'website': 'https://github.com/yourusername/odoo-dev-mcp',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'external_dependencies': {
        'python': [
            'mcp',
            'psycopg2',
            'pyyaml',
            'requests',
            'pydantic',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/mcp_data.xml',
        'views/mcp_config_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
