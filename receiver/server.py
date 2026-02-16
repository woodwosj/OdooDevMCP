# -*- coding: utf-8 -*-
"""
Standalone Flask webhook receiver for Odoo MCP registration.
Receives registration and heartbeat messages from Odoo MCP servers.
"""

import argparse
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory storage for registered servers
servers = {}
servers_lock = threading.Lock()

# Track server startup time for uptime calculation
startup_time = time.time()


def get_current_timestamp():
    """Generate UTC ISO timestamp with 'Z' suffix."""
    return datetime.utcnow().isoformat() + 'Z'


def is_stale(last_seen_str, threshold_seconds=120):
    """Check if a server is stale based on last_seen timestamp."""
    try:
        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', ''))
        now = datetime.utcnow()
        delta = (now - last_seen).total_seconds()
        return delta > threshold_seconds
    except (ValueError, AttributeError):
        return True


@app.route('/register', methods=['POST'])
def register():
    """Register a new MCP server."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON payload provided'}), 400

    if 'server_id' not in data:
        return jsonify({'error': 'Missing required field: server_id'}), 400

    server_id = data['server_id']
    now = get_current_timestamp()

    # Store full payload with additional metadata
    server_record = {
        **data,
        'registered_at': now,
        'last_seen': now,
        'heartbeat_count': 0
    }

    with servers_lock:
        servers[server_id] = server_record

    return jsonify({
        'status': 'registered',
        'server_id': server_id
    }), 201


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Receive heartbeat from a registered server."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON payload provided'}), 400

    if 'server_id' not in data:
        return jsonify({'error': 'Missing required field: server_id'}), 400

    server_id = data['server_id']

    with servers_lock:
        if server_id not in servers:
            # Create minimal entry for unknown server
            servers[server_id] = {
                'server_id': server_id,
                'last_seen': get_current_timestamp(),
                'heartbeat_count': 1,
            }
        else:
            # Update existing server
            servers[server_id]['last_seen'] = get_current_timestamp()
            servers[server_id]['heartbeat_count'] += 1

        heartbeat_count = servers[server_id]['heartbeat_count']

    return jsonify({
        'status': 'ok',
        'server_id': server_id,
        'heartbeat_count': heartbeat_count
    }), 200


@app.route('/servers', methods=['GET'])
def list_servers():
    """List all registered servers with staleness indicator."""
    with servers_lock:
        server_list = []
        for server_id, server_data in servers.items():
            last_seen = server_data.get('last_seen', '')
            server_list.append({
                'server_id': server_id,
                'hostname': server_data.get('hostname', ''),
                'database': server_data.get('database', ''),
                'last_seen': last_seen,
                'heartbeat_count': server_data.get('heartbeat_count', 0),
                'stale': is_stale(last_seen)
            })

    return jsonify({
        'servers': server_list,
        'count': len(server_list)
    }), 200


@app.route('/servers/<server_id>', methods=['GET'])
def get_server(server_id):
    """Get full details for a specific server."""
    with servers_lock:
        if server_id not in servers:
            return jsonify({
                'error': 'Server not found',
                'server_id': server_id
            }), 404

        server_data = servers[server_id].copy()

    return jsonify(server_data), 200


@app.route('/servers/<server_id>', methods=['DELETE'])
def delete_server(server_id):
    """Remove a server from the registry."""
    with servers_lock:
        if server_id not in servers:
            return jsonify({
                'error': 'Server not found',
                'server_id': server_id
            }), 404

        del servers[server_id]

    return jsonify({
        'status': 'deleted',
        'server_id': server_id
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint with uptime and server count."""
    uptime = int(time.time() - startup_time)

    with servers_lock:
        server_count = len(servers)

    return jsonify({
        'status': 'healthy',
        'uptime_seconds': uptime,
        'server_count': server_count
    }), 200


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='Flask webhook receiver for Odoo MCP registration'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run the Flask server on (default: 5000)'
    )
    parser.add_argument(
        '--ngrok',
        action='store_true',
        help='Start ngrok tunnel for public access'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run Flask in debug mode'
    )

    args = parser.parse_args()

    # Start ngrok tunnel if requested
    if args.ngrok:
        try:
            from pyngrok import ngrok
            tunnel = ngrok.connect(args.port)
            print(f"ngrok tunnel URL: {tunnel.public_url}")
            print(f"Register endpoint: {tunnel.public_url}/register")
        except ImportError:
            print("Error: pyngrok not installed. Install with: pip install pyngrok")
            return
        except Exception as e:
            print(f"Error starting ngrok: {e}")
            return

    # Start Flask server
    print(f"Starting Flask receiver server on port {args.port}")
    print(f"Endpoints available:")
    print(f"  POST /register")
    print(f"  POST /heartbeat")
    print(f"  GET  /servers")
    print(f"  GET  /servers/<server_id>")
    print(f"  DELETE /servers/<server_id>")
    print(f"  GET  /health")

    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
