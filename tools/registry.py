# -*- coding: utf-8 -*-
"""Tool registry that maps MCP tool calls to handler functions."""

import logging
from typing import Dict, Callable, Any

from . import terminal, database, filesystem, odoo_tools

_logger = logging.getLogger(__name__)


def get_tool_registry() -> Dict[str, Callable]:
    """Get the registry of available MCP tools.

    Returns:
        dict: Mapping of tool names to handler functions
    """
    return {
        # Terminal tools
        'execute_command': terminal.execute_command,

        # Database tools
        'query_database': database.query_database,
        'execute_sql': database.execute_sql,
        'get_db_schema': database.get_db_schema,

        # Filesystem tools
        'read_file': filesystem.read_file,
        'write_file': filesystem.write_file,

        # Odoo tools
        'odoo_shell': odoo_tools.odoo_shell_exec,
        'service_status': odoo_tools.service_status,
        'read_config': odoo_tools.read_config,
        'list_modules': odoo_tools.list_modules,
        'get_module_info': odoo_tools.get_module_info,
        'install_module': odoo_tools.install_module,
        'upgrade_module': odoo_tools.upgrade_module,
    }


def get_tool_schemas() -> Dict[str, Dict]:
    """Get JSON schemas for all available tools.

    Returns:
        dict: Mapping of tool names to their JSON schemas
    """
    return {
        'execute_command': {
            'description': 'Execute a shell command on the Odoo server',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {
                        'type': 'string',
                        'description': 'The shell command to execute',
                    },
                    'working_directory': {
                        'type': 'string',
                        'description': 'Working directory for command execution',
                    },
                    'timeout': {
                        'type': 'integer',
                        'description': 'Maximum execution time in seconds',
                        'default': 30,
                    },
                    'env_vars': {
                        'type': 'object',
                        'description': 'Additional environment variables',
                    },
                },
                'required': ['command'],
            },
        },
        'query_database': {
            'description': 'Execute a read-only SQL query against the Odoo PostgreSQL database',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'SQL query to execute (SELECT or read-only)',
                    },
                    'params': {
                        'type': 'array',
                        'description': 'Parameterized query values',
                        'items': {},
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Maximum number of rows to return',
                        'default': 1000,
                    },
                },
                'required': ['query'],
            },
        },
        'execute_sql': {
            'description': 'Execute a write SQL statement (INSERT, UPDATE, DELETE, DDL)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'statement': {
                        'type': 'string',
                        'description': 'SQL statement to execute',
                    },
                    'params': {
                        'type': 'array',
                        'description': 'Parameterized query values',
                        'items': {},
                    },
                },
                'required': ['statement'],
            },
        },
        'get_db_schema': {
            'description': 'Retrieve database schema information',
            'parameters': {
                'type': 'object',
                'properties': {
                    'action': {
                        'type': 'string',
                        'enum': ['list_tables', 'describe_table', 'list_indexes', 'list_constraints'],
                        'description': 'What schema information to retrieve',
                    },
                    'table_name': {
                        'type': 'string',
                        'description': 'Table name (required for describe_table, list_indexes, list_constraints)',
                    },
                    'schema_name': {
                        'type': 'string',
                        'description': 'PostgreSQL schema',
                        'default': 'public',
                    },
                },
                'required': ['action'],
            },
        },
        'read_file': {
            'description': 'Read the contents of a file from the Odoo server filesystem',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Absolute path to the file to read',
                    },
                    'encoding': {
                        'type': 'string',
                        'description': 'Text encoding (use "binary" for base64 output)',
                        'default': 'utf-8',
                    },
                    'offset': {
                        'type': 'integer',
                        'description': 'Line number to start reading from (1-based)',
                        'default': 0,
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Maximum number of lines to return (0 = entire file)',
                        'default': 0,
                    },
                },
                'required': ['path'],
            },
        },
        'write_file': {
            'description': 'Write content to a file on the Odoo server filesystem',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {
                        'type': 'string',
                        'description': 'Absolute path to the file to write',
                    },
                    'content': {
                        'type': 'string',
                        'description': 'Content to write',
                    },
                    'encoding': {
                        'type': 'string',
                        'description': 'Text encoding (use "binary" for base64 input)',
                        'default': 'utf-8',
                    },
                    'mode': {
                        'type': 'string',
                        'enum': ['overwrite', 'append'],
                        'description': 'Write mode',
                        'default': 'overwrite',
                    },
                    'create_directories': {
                        'type': 'boolean',
                        'description': 'Create parent directories if they do not exist',
                        'default': True,
                    },
                },
                'required': ['path', 'content'],
            },
        },
        'odoo_shell': {
            'description': 'Execute Python code in the Odoo environment with ORM access',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {
                        'type': 'string',
                        'description': 'Python code to execute (env variable is available)',
                    },
                    'timeout': {
                        'type': 'integer',
                        'description': 'Maximum execution time in seconds',
                        'default': 30,
                    },
                },
                'required': ['code'],
            },
        },
        'service_status': {
            'description': 'Check and manage services (odoo, postgresql, nginx)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'service': {
                        'type': 'string',
                        'description': 'Service name',
                        'default': 'odoo',
                    },
                    'action': {
                        'type': 'string',
                        'enum': ['status', 'start', 'stop', 'restart', 'logs'],
                        'description': 'Action to perform',
                        'default': 'status',
                    },
                    'log_lines': {
                        'type': 'integer',
                        'description': 'Number of log lines to return (for logs action)',
                        'default': 50,
                    },
                },
            },
        },
        'read_config': {
            'description': 'Read the Odoo server configuration file',
            'parameters': {
                'type': 'object',
                'properties': {
                    'key': {
                        'type': 'string',
                        'description': 'Specific configuration key to read (null = all)',
                    },
                },
            },
        },
        'list_modules': {
            'description': 'List Odoo modules with their installation status',
            'parameters': {
                'type': 'object',
                'properties': {
                    'state': {
                        'type': 'string',
                        'enum': ['installed', 'uninstalled', 'to_upgrade', 'to_install', 'to_remove', 'all'],
                        'description': 'Filter by module state',
                        'default': 'all',
                    },
                    'search': {
                        'type': 'string',
                        'description': 'Search term to filter module names or descriptions',
                    },
                    'limit': {
                        'type': 'integer',
                        'description': 'Maximum number of modules to return',
                        'default': 100,
                    },
                },
            },
        },
        'get_module_info': {
            'description': 'Get detailed information about a specific module',
            'parameters': {
                'type': 'object',
                'properties': {
                    'module_name': {
                        'type': 'string',
                        'description': 'Technical name of the module',
                    },
                },
                'required': ['module_name'],
            },
        },
        'install_module': {
            'description': 'Install an Odoo module',
            'parameters': {
                'type': 'object',
                'properties': {
                    'module_name': {
                        'type': 'string',
                        'description': 'Technical name of the module to install',
                    },
                },
                'required': ['module_name'],
            },
        },
        'upgrade_module': {
            'description': 'Upgrade an Odoo module',
            'parameters': {
                'type': 'object',
                'properties': {
                    'module_name': {
                        'type': 'string',
                        'description': 'Technical name of the module to upgrade',
                    },
                },
                'required': ['module_name'],
            },
        },
    }


def call_tool(env, tool_name: str, parameters: Dict[str, Any]) -> Any:
    """Call a tool by name with given parameters.

    Args:
        env: Odoo environment
        tool_name: Name of the tool to call
        parameters: Parameters to pass to the tool

    Returns:
        Tool execution result

    Raises:
        ValueError: If tool not found
    """
    registry = get_tool_registry()

    if tool_name not in registry:
        raise ValueError(f"Unknown tool: {tool_name}")

    handler = registry[tool_name]

    # All tool handlers receive env as first parameter
    return handler(env, **parameters)
