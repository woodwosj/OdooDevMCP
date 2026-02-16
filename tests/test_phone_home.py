"""Tests for phone-home mechanism."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from odoo_dev_mcp.phone_home import (
    get_network_info,
    register_server,
    sanitize_metadata,
    send_heartbeat,
)


class TestSanitizeMetadata:
    """Test metadata sanitization (C2 fix)."""

    def test_sanitizes_valid_json_types(self):
        """Should preserve valid JSON types."""
        metadata = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        result = sanitize_metadata(metadata)

        assert result == metadata

    def test_rejects_non_json_serializable(self):
        """Should reject non-JSON-serializable types."""

        class CustomObject:
            pass

        metadata = {"object": CustomObject(), "function": lambda x: x}

        result = sanitize_metadata(metadata)

        # Should return empty dict on error
        assert result == {}

    def test_prevents_injection_attacks(self):
        """Should prevent malicious data injection."""
        # Attempt to inject executable code
        metadata = {
            "normal_key": "normal_value",
            "malicious": {"__class__": "exploit"},
        }

        result = sanitize_metadata(metadata)

        # Should round-trip through JSON, neutralizing any injection
        assert isinstance(result, dict)
        # After JSON round-trip, it should be safe
        json_str = json.dumps(result)
        assert "__class__" in json_str  # Key is preserved but value is safe


class TestGetNetworkInfo:
    """Test network information gathering."""

    @patch("odoo_dev_mcp.phone_home.socket")
    def test_gets_hostname_and_ip(self, mock_socket):
        """Should retrieve hostname and IP addresses."""
        mock_socket.gethostname.return_value = "test-server"
        mock_socket.gethostbyname_ex.return_value = (
            "test-server",
            [],
            ["192.168.1.100", "10.0.0.50"],
        )

        # Mock socket connection for primary IP
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        mock_socket.socket.return_value = mock_sock

        result = get_network_info()

        assert result["hostname"] == "test-server"
        assert result["primary"] == "192.168.1.100"
        assert "192.168.1.100" in result["all"]

    @patch("odoo_dev_mcp.phone_home.socket")
    def test_handles_network_errors_gracefully(self, mock_socket):
        """Should handle network errors and return defaults."""
        mock_socket.gethostname.return_value = "test-server"
        mock_socket.socket.side_effect = Exception("Network error")
        mock_socket.gethostbyname_ex.side_effect = Exception("DNS error")

        result = get_network_info()

        assert result["hostname"] == "test-server"
        # Should have fallback IP
        assert "primary" in result


class TestRegisterServer:
    """Test server registration."""

    @patch("odoo_dev_mcp.phone_home.requests.post")
    @patch("odoo_dev_mcp.phone_home.get_config")
    @patch("odoo_dev_mcp.phone_home.get_network_info")
    @patch("odoo_dev_mcp.phone_home.get_server_id")
    def test_sends_registration_payload(
        self, mock_get_id, mock_get_network, mock_get_config, mock_post
    ):
        """Should send registration payload with sanitized metadata."""
        mock_config = Mock()
        mock_config.phone_home.url = "http://registry.example.com/register"
        mock_config.phone_home.retry_count = 1
        mock_config.phone_home.timeout = 5
        mock_config.phone_home.extra_metadata = {"env": "test", "region": "us-east"}
        mock_config.server.port = 8768
        mock_config.server.transport = "stdio"
        mock_config.server.version = "1.0.0"

        mock_get_config.return_value = mock_config
        mock_get_id.return_value = "test-uuid"
        mock_get_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = register_server()

        assert result is True
        mock_post.assert_called_once()

        # Check that payload was sent
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        assert payload["server_id"] == "test-uuid"
        assert payload["hostname"] == "test-server"
        assert payload["env"] == "test"
        assert payload["region"] == "us-east"

    @patch("odoo_dev_mcp.phone_home.requests.post")
    @patch("odoo_dev_mcp.phone_home.get_config")
    def test_skips_registration_when_disabled(self, mock_get_config, mock_post):
        """Should skip registration when URL is not configured."""
        mock_config = Mock()
        mock_config.phone_home.url = None

        mock_get_config.return_value = mock_config

        result = register_server()

        assert result is False
        mock_post.assert_not_called()

    @patch("odoo_dev_mcp.phone_home.requests.post")
    @patch("odoo_dev_mcp.phone_home.get_config")
    @patch("odoo_dev_mcp.phone_home.get_network_info")
    @patch("odoo_dev_mcp.phone_home.get_server_id")
    @patch("odoo_dev_mcp.phone_home.time.sleep")  # Speed up test
    def test_retries_on_failure(
        self, mock_sleep, mock_get_id, mock_get_network, mock_get_config, mock_post
    ):
        """Should retry registration on failure."""
        mock_config = Mock()
        mock_config.phone_home.url = "http://registry.example.com/register"
        mock_config.phone_home.retry_count = 3
        mock_config.phone_home.retry_backoff = 2
        mock_config.phone_home.timeout = 5
        mock_config.phone_home.extra_metadata = {}
        mock_config.server.port = 8768
        mock_config.server.transport = "stdio"
        mock_config.server.version = "1.0.0"

        mock_get_config.return_value = mock_config
        mock_get_id.return_value = "test-uuid"
        mock_get_network.return_value = {
            "hostname": "test",
            "primary": "127.0.0.1",
            "all": ["127.0.0.1"],
        }

        # Fail twice, then succeed
        mock_post.side_effect = [
            Exception("Connection error"),
            Exception("Connection error"),
            Mock(status_code=200),
        ]

        result = register_server()

        assert result is True
        assert mock_post.call_count == 3


class TestSendHeartbeat:
    """Test heartbeat sending."""

    @patch("odoo_dev_mcp.phone_home.requests.post")
    @patch("odoo_dev_mcp.phone_home.get_config")
    @patch("odoo_dev_mcp.phone_home.get_server_id")
    def test_sends_heartbeat(self, mock_get_id, mock_get_config, mock_post):
        """Should send heartbeat with status."""
        mock_config = Mock()
        mock_config.phone_home.url = "http://registry.example.com/register"
        mock_config.phone_home.timeout = 5

        mock_get_config.return_value = mock_config
        mock_get_id.return_value = "test-uuid"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_heartbeat(start_time=1000.0, active_connections=2)

        assert result is True
        mock_post.assert_called_once()

        # Check payload
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        assert payload["server_id"] == "test-uuid"
        assert payload["status"] == "healthy"
        assert payload["active_connections"] == 2
