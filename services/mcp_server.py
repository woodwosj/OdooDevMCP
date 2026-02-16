# -*- coding: utf-8 -*-
"""Core MCP protocol handler (JSON-RPC over HTTP)."""

import json
import logging
from typing import Dict, Any, Optional

from ..tools.registry import get_tool_registry, get_tool_schemas, call_tool

_logger = logging.getLogger(__name__)


class MCPServerHandler:
    """MCP Server handler for processing JSON-RPC requests."""

    def __init__(self, env, http_request):
        """Initialize MCP server handler.

        Args:
            env: Odoo environment
            http_request: HTTP request object (for future SSE support)
        """
        self.env = env
        self.http_request = http_request
        self.tool_registry = get_tool_registry()
        self.tool_schemas = get_tool_schemas()

    def handle_request(self, jsonrpc_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC MCP request.

        Args:
            jsonrpc_request: JSON-RPC request object

        Returns:
            JSON-RPC response object
        """
        try:
            # Validate JSON-RPC structure
            if not isinstance(jsonrpc_request, dict):
                return self._error_response(
                    -32600,
                    "Invalid Request",
                    "Request must be a JSON object",
                    None
                )

            jsonrpc = jsonrpc_request.get('jsonrpc')
            method = jsonrpc_request.get('method')
            request_id = jsonrpc_request.get('id')

            if jsonrpc != '2.0':
                return self._error_response(
                    -32600,
                    "Invalid Request",
                    "jsonrpc must be '2.0'",
                    request_id
                )

            if not method:
                return self._error_response(
                    -32600,
                    "Invalid Request",
                    "method is required",
                    request_id
                )

            # Route to appropriate handler
            if method == 'tools/list':
                return self._handle_tools_list(request_id)
            elif method == 'tools/call':
                params = jsonrpc_request.get('params', {})
                return self._handle_tools_call(params, request_id)
            elif method == 'resources/list':
                return self._handle_resources_list(request_id)
            elif method == 'resources/read':
                params = jsonrpc_request.get('params', {})
                return self._handle_resources_read(params, request_id)
            elif method == 'initialize':
                return self._handle_initialize(request_id)
            else:
                return self._error_response(
                    -32601,
                    "Method not found",
                    f"Unknown method: {method}",
                    request_id
                )

        except Exception as e:
            _logger.error(f"MCP request handling error: {e}", exc_info=True)
            return self._error_response(
                -32603,
                "Internal error",
                str(e),
                jsonrpc_request.get('id')
            )

    def _handle_initialize(self, request_id) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        return {
            'jsonrpc': '2.0',
            'result': {
                'protocolVersion': '2024-11-05',
                'serverInfo': {
                    'name': 'odoo-dev-mcp',
                    'version': '1.0.0',
                },
                'capabilities': {
                    'tools': {},
                    'resources': {},
                },
            },
            'id': request_id,
        }

    def _handle_tools_list(self, request_id) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []
        for tool_name, schema in self.tool_schemas.items():
            tools.append({
                'name': tool_name,
                'description': schema.get('description', ''),
                'inputSchema': schema.get('parameters', {}),
            })

        return {
            'jsonrpc': '2.0',
            'result': {
                'tools': tools,
            },
            'id': request_id,
        }

    def _handle_tools_call(self, params: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle tools/call request."""
        try:
            tool_name = params.get('name')
            tool_params = params.get('arguments', {})

            if not tool_name:
                return self._error_response(
                    -32602,
                    "Invalid params",
                    "Tool name is required",
                    request_id
                )

            if tool_name not in self.tool_registry:
                return self._error_response(
                    -32602,
                    "Invalid params",
                    f"Unknown tool: {tool_name}",
                    request_id
                )

            _logger.info(f"MCP: Calling tool {tool_name}")

            # Call the tool
            result = call_tool(self.env, tool_name, tool_params)

            return {
                'jsonrpc': '2.0',
                'result': {
                    'content': [
                        {
                            'type': 'text',
                            'text': json.dumps(result, indent=2),
                        }
                    ],
                },
                'id': request_id,
            }

        except Exception as e:
            _logger.error(f"Tool execution error: {e}", exc_info=True)
            return self._error_response(
                -32603,
                "Tool execution failed",
                str(e),
                request_id
            )

    def _handle_resources_list(self, request_id) -> Dict[str, Any]:
        """Handle resources/list request."""
        resources = [
            {
                'uri': 'odoo://config',
                'name': 'Odoo Configuration',
                'description': 'Current Odoo server configuration (with sensitive values masked)',
                'mimeType': 'application/json',
            },
            {
                'uri': 'odoo://logs/{service}',
                'name': 'Service Logs',
                'description': 'Recent log entries for the specified service',
                'mimeType': 'text/plain',
            },
            {
                'uri': 'odoo://schema/{table}',
                'name': 'Database Schema',
                'description': 'Schema information for a specific database table',
                'mimeType': 'application/json',
            },
            {
                'uri': 'odoo://modules',
                'name': 'Installed Modules',
                'description': 'List of all installed Odoo modules with version info',
                'mimeType': 'application/json',
            },
            {
                'uri': 'odoo://system',
                'name': 'System Information',
                'description': 'System information -- OS, disk, memory, Odoo version, Python version',
                'mimeType': 'application/json',
            },
        ]

        return {
            'jsonrpc': '2.0',
            'result': {
                'resources': resources,
            },
            'id': request_id,
        }

    def _handle_resources_read(self, params: Dict[str, Any], request_id) -> Dict[str, Any]:
        """Handle resources/read request."""
        try:
            uri = params.get('uri')
            if not uri:
                return self._error_response(
                    -32602,
                    "Invalid params",
                    "Resource URI is required",
                    request_id
                )

            # Parse URI and delegate to appropriate resource provider
            from ..tools import odoo_tools

            content = ""
            mime_type = "text/plain"

            if uri == 'odoo://config':
                config_data = odoo_tools.read_config(self.env)
                content = json.dumps(config_data, indent=2)
                mime_type = "application/json"

            elif uri.startswith('odoo://logs/'):
                service_name = uri.split('/')[-1]
                logs_data = odoo_tools.service_status(
                    self.env,
                    service=service_name,
                    action='logs',
                    log_lines=100
                )
                content = "\n".join(logs_data.get("log_lines", []))
                mime_type = "text/plain"

            elif uri.startswith('odoo://schema/'):
                table_name = uri.split('/')[-1]
                from ..tools import database
                schema_data = database.get_db_schema(
                    self.env,
                    action='describe_table',
                    table_name=table_name
                )
                content = json.dumps(schema_data, indent=2)
                mime_type = "application/json"

            elif uri == 'odoo://modules':
                modules_data = odoo_tools.list_modules(self.env, state='installed', limit=1000)
                content = json.dumps(modules_data, indent=2)
                mime_type = "application/json"

            elif uri == 'odoo://system':
                import platform
                import socket
                system_info = {
                    'hostname': socket.gethostname(),
                    'os': platform.system() + " " + platform.release(),
                    'python_version': platform.python_version(),
                    'odoo_version': self.env.registry.version,
                }
                content = json.dumps(system_info, indent=2)
                mime_type = "application/json"

            else:
                return self._error_response(
                    -32602,
                    "Invalid params",
                    f"Unknown resource URI: {uri}",
                    request_id
                )

            return {
                'jsonrpc': '2.0',
                'result': {
                    'contents': [
                        {
                            'uri': uri,
                            'mimeType': mime_type,
                            'text': content,
                        }
                    ],
                },
                'id': request_id,
            }

        except Exception as e:
            _logger.error(f"Resource read error: {e}", exc_info=True)
            return self._error_response(
                -32603,
                "Resource read failed",
                str(e),
                request_id
            )

    def _error_response(
        self,
        code: int,
        message: str,
        data: Optional[str] = None,
        request_id: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Build a JSON-RPC error response."""
        error = {
            'code': code,
            'message': message,
        }
        if data is not None:
            error['data'] = data

        return {
            'jsonrpc': '2.0',
            'error': error,
            'id': request_id,
        }
