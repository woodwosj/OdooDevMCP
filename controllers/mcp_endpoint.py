# -*- coding: utf-8 -*-

import json
import logging
from odoo import http, release
from odoo.http import request, Response
from werkzeug.exceptions import BadRequest

from ..services.mcp_server import MCPServerHandler
from ..tools.registry import get_tool_registry

_logger = logging.getLogger(__name__)


class MCPController(http.Controller):
    """HTTP controller that exposes MCP protocol over HTTP.

    Uses Odoo 19's native ``auth='bearer'`` which authenticates via
    the ``Authorization: Bearer <api_key>`` header against Odoo API keys.
    Falls back to session auth when the header is absent.
    """

    @http.route('/mcp/v1', type='http', auth='bearer', methods=['POST'], csrf=False)
    def mcp_endpoint(self, **kwargs):
        """Main MCP JSON-RPC endpoint.

        Uses type='http' instead of type='jsonrpc' so we control the full
        request/response cycle.  Odoo's jsonrpc type auto-wraps the return
        value in its own JSON-RPC envelope, which double-wraps the response
        that MCPServerHandler already builds.  Claude Code's MCP HTTP
        transport expects a clean, single JSON-RPC response.
        """
        request_id = None
        try:
            # Parse the raw JSON body ourselves
            raw_data = request.httprequest.get_data(as_text=True)
            if not raw_data:
                return Response(
                    json.dumps({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32700,
                            'message': 'Parse error',
                            'data': 'Empty request body',
                        },
                        'id': None,
                    }),
                    content_type='application/json',
                    status=200,
                )

            try:
                jsonrpc_request = json.loads(raw_data)
            except (json.JSONDecodeError, ValueError) as parse_err:
                return Response(
                    json.dumps({
                        'jsonrpc': '2.0',
                        'error': {
                            'code': -32700,
                            'message': 'Parse error',
                            'data': str(parse_err),
                        },
                        'id': None,
                    }),
                    content_type='application/json',
                    status=200,
                )

            request_id = jsonrpc_request.get('id')

            _logger.debug(f"MCP: Received request: {jsonrpc_request.get('method')}")

            # Create MCP server handler
            handler = MCPServerHandler(request.env, request.httprequest)

            # Process request – handler returns a full JSON-RPC response dict
            result = handler.handle_request(jsonrpc_request)

            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200,
            )

        except Exception as e:
            _logger.error(f"MCP: Error handling request: {e}", exc_info=True)
            return Response(
                json.dumps({
                    'jsonrpc': '2.0',
                    'error': {
                        'code': -32603,
                        'message': 'Internal error',
                        'data': str(e),
                    },
                    'id': request_id,
                }),
                content_type='application/json',
                status=200,
            )

    @http.route('/mcp/v1/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self):
        """Health check endpoint (unauthenticated)."""
        try:
            return Response(
                json.dumps({
                    'status': 'healthy',
                    'version': '1.0.0',
                    'odoo_version': release.version
                }),
                content_type='application/json',
                status=200
            )
        except Exception as e:
            _logger.error(f"MCP: Health check failed: {e}")
            return Response(
                json.dumps({
                    'status': 'unhealthy',
                    'error': str(e)
                }),
                content_type='application/json',
                status=500
            )

    @http.route('/mcp/v1/capabilities', type='http', auth='bearer', methods=['GET'], csrf=False)
    def capabilities(self):
        """Return list of available MCP tools (authenticated)."""
        try:
            capabilities = {
                'version': '1.0.0',
                'transport': 'http',
                'tools': list(get_tool_registry().keys()),
                'resources': [
                    'odoo://config',
                    'odoo://logs/{service}',
                    'odoo://schema/{table}',
                    'odoo://modules',
                    'odoo://system',
                ]
            }

            return Response(
                json.dumps(capabilities, indent=2),
                content_type='application/json',
                status=200
            )

        except Exception as e:
            _logger.error(f"MCP: Error getting capabilities: {e}")
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=500
            )
