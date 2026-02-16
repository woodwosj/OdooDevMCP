"""Tests for the standalone Flask receiver server heartbeat merge functionality."""

import json
import pytest

flask = pytest.importorskip("flask", reason="Flask not installed")


@pytest.fixture
def receiver_app():
    """Create a test client for the receiver Flask app."""
    # Import the receiver app
    import sys
    from pathlib import Path

    receiver_path = Path(__file__).parent.parent / "receiver"
    sys.path.insert(0, str(receiver_path))

    from server import app, servers, servers_lock

    # Clear servers before each test
    with servers_lock:
        servers.clear()

    app.config['TESTING'] = True
    client = app.test_client()

    yield client

    # Clean up
    with servers_lock:
        servers.clear()


class TestReceiverHeartbeatMerge:

    def test_enriched_heartbeat_updates_server_record(self, receiver_app):
        """Enriched heartbeat should merge new fields into existing record."""
        # Register a server first
        register_payload = {
            "server_id": "test_db_host1",
            "hostname": "old-hostname",
            "ip_addresses": {"primary": "192.168.1.100", "all": ["192.168.1.100"]},
            "port": 8768,
            "transport": "http/sse",
            "version": "1.0.0",
            "odoo_version": "19.0",
            "database": "test_db",
            "capabilities": ["execute_command", "query_database"],
            "odoo_stage": "dev",
            "started_at": "2024-01-01T00:00:00Z"
        }

        response = receiver_app.post('/register', json=register_payload)
        assert response.status_code == 201

        # Send enriched heartbeat with updated hostname
        heartbeat_payload = {
            "server_id": "test_db_host1",
            "hostname": "new-hostname",
            "ip_addresses": {"primary": "192.168.1.200", "all": ["192.168.1.200"]},
            "port": 8768,
            "transport": "http/sse",
            "version": "1.0.0",
            "odoo_version": "19.0",
            "database": "test_db",
            "capabilities": ["execute_command", "query_database", "read_file"],
            "odoo_stage": "production",
            "status": "healthy",
            "timestamp": "2024-01-01T01:00:00Z",
            "uptime_seconds": 3600.0
        }

        response = receiver_app.post('/heartbeat', json=heartbeat_payload)
        assert response.status_code == 200

        # Verify the server record was updated
        response = receiver_app.get('/servers/test_db_host1')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['hostname'] == 'new-hostname'
        assert data['ip_addresses']['primary'] == '192.168.1.200'
        assert data['odoo_stage'] == 'production'
        assert data['capabilities'] == ["execute_command", "query_database", "read_file"]
        assert data['heartbeat_count'] == 1

        # Metadata fields should be preserved
        assert 'registered_at' in data
        assert 'last_seen' in data

    def test_slim_heartbeat_preserves_existing_record(self, receiver_app):
        """Slim heartbeat (only server_id, status, timestamp) should not overwrite existing fields."""
        # Register a server first
        register_payload = {
            "server_id": "test_db_host2",
            "hostname": "original-hostname",
            "ip_addresses": {"primary": "192.168.1.100", "all": ["192.168.1.100"]},
            "port": 8768,
            "transport": "http/sse",
            "version": "1.0.0",
            "odoo_version": "19.0",
            "database": "test_db",
            "capabilities": ["execute_command"],
            "odoo_stage": "dev",
            "started_at": "2024-01-01T00:00:00Z"
        }

        response = receiver_app.post('/register', json=register_payload)
        assert response.status_code == 201

        # Send slim heartbeat
        heartbeat_payload = {
            "server_id": "test_db_host2",
            "status": "healthy",
            "timestamp": "2024-01-01T01:00:00Z"
        }

        response = receiver_app.post('/heartbeat', json=heartbeat_payload)
        assert response.status_code == 200

        # Verify the server record preserves original fields
        response = receiver_app.get('/servers/test_db_host2')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['hostname'] == 'original-hostname'
        assert data['ip_addresses']['primary'] == '192.168.1.100'
        assert data['odoo_stage'] == 'dev'
        assert data['capabilities'] == ["execute_command"]
        assert data['heartbeat_count'] == 1

    def test_unknown_server_with_enriched_heartbeat(self, receiver_app):
        """Unknown server receiving enriched heartbeat should create full record."""
        # Send enriched heartbeat for unknown server
        heartbeat_payload = {
            "server_id": "test_db_host3",
            "hostname": "new-server",
            "ip_addresses": {"primary": "192.168.1.150", "all": ["192.168.1.150"]},
            "port": 8768,
            "transport": "http/sse",
            "version": "1.0.0",
            "odoo_version": "19.0",
            "database": "test_db",
            "capabilities": ["execute_command", "query_database"],
            "odoo_stage": "staging",
            "status": "healthy",
            "timestamp": "2024-01-01T01:00:00Z",
            "uptime_seconds": 1800.0
        }

        response = receiver_app.post('/heartbeat', json=heartbeat_payload)
        assert response.status_code == 200

        # Verify the server record was created with all fields
        response = receiver_app.get('/servers/test_db_host3')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['server_id'] == 'test_db_host3'
        assert data['hostname'] == 'new-server'
        assert data['ip_addresses']['primary'] == '192.168.1.150'
        assert data['odoo_stage'] == 'staging'
        assert data['capabilities'] == ["execute_command", "query_database"]
        assert data['heartbeat_count'] == 1

    def test_multiple_heartbeats_increment_count(self, receiver_app):
        """Multiple heartbeats should increment heartbeat_count."""
        # Register a server
        register_payload = {
            "server_id": "test_db_host4",
            "hostname": "test-hostname",
            "started_at": "2024-01-01T00:00:00Z"
        }

        response = receiver_app.post('/register', json=register_payload)
        assert response.status_code == 201

        # Send multiple heartbeats
        for i in range(5):
            heartbeat_payload = {
                "server_id": "test_db_host4",
                "status": "healthy",
                "timestamp": f"2024-01-01T{i:02d}:00:00Z"
            }
            response = receiver_app.post('/heartbeat', json=heartbeat_payload)
            assert response.status_code == 200

        # Verify heartbeat count
        response = receiver_app.get('/servers/test_db_host4')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['heartbeat_count'] == 5

    def test_partial_enriched_fields(self, receiver_app):
        """Heartbeat with some enriched fields should only update those fields."""
        # Register a server
        register_payload = {
            "server_id": "test_db_host5",
            "hostname": "original-hostname",
            "ip_addresses": {"primary": "192.168.1.100", "all": ["192.168.1.100"]},
            "port": 8768,
            "capabilities": ["execute_command"],
            "odoo_stage": "dev"
        }

        response = receiver_app.post('/register', json=register_payload)
        assert response.status_code == 201

        # Send heartbeat with only some enriched fields
        heartbeat_payload = {
            "server_id": "test_db_host5",
            "hostname": "updated-hostname",
            "capabilities": ["execute_command", "query_database"],
            "status": "healthy",
            "timestamp": "2024-01-01T01:00:00Z"
        }

        response = receiver_app.post('/heartbeat', json=heartbeat_payload)
        assert response.status_code == 200

        # Verify partial update
        response = receiver_app.get('/servers/test_db_host5')
        assert response.status_code == 200

        data = json.loads(response.data)
        # Updated fields
        assert data['hostname'] == 'updated-hostname'
        assert data['capabilities'] == ["execute_command", "query_database"]
        # Preserved fields
        assert data['ip_addresses']['primary'] == '192.168.1.100'
        assert data['port'] == 8768
        assert data['odoo_stage'] == 'dev'
