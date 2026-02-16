"""Tests for phone-home mechanism (register_server, send_heartbeat, get_network_info)."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from OdooDevMCP.services.phone_home import (
    _build_server_payload,
    get_network_info,
    get_server_hostname,
    register_server,
    send_heartbeat,
)


# ---------------------------------------------------------------------------
# get_network_info (standalone, no env needed)
# ---------------------------------------------------------------------------

class TestGetNetworkInfo:

    @patch("OdooDevMCP.services.phone_home.socket")
    def test_gets_hostname_and_ip(self, mock_socket):
        mock_socket.gethostname.return_value = "test-server"
        mock_socket.AF_INET = 2
        mock_socket.SOCK_DGRAM = 2

        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        mock_socket.socket.return_value = mock_sock

        mock_socket.gethostbyname_ex.return_value = (
            "test-server",
            [],
            ["192.168.1.100", "10.0.0.50"],
        )

        result = get_network_info()

        assert result["hostname"] == "test-server"
        assert result["primary"] == "192.168.1.100"
        assert "192.168.1.100" in result["all"]

    @patch("OdooDevMCP.services.phone_home.socket")
    def test_handles_network_errors_gracefully(self, mock_socket):
        mock_socket.gethostname.return_value = "test-server"
        mock_socket.AF_INET = 2
        mock_socket.SOCK_DGRAM = 2
        mock_socket.socket.side_effect = Exception("Network error")
        mock_socket.gethostbyname_ex.side_effect = Exception("DNS error")

        result = get_network_info()

        assert result["hostname"] == "test-server"
        assert result["primary"] == "127.0.0.1"


# ---------------------------------------------------------------------------
# register_server
# ---------------------------------------------------------------------------

class TestRegisterServer:

    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_sends_registration_payload(self, mock_network, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_retry_count"] = "1"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = register_server(mock_env)

        assert result is True
        mock_post.assert_called_once()

        # Verify payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["server_id"] == "test_db_test-server"
        assert payload["hostname"] == "test-server"
        assert payload["database"] == "test_db"
        assert "capabilities" in payload

        # URL should have /register appended
        called_url = mock_post.call_args[0][0]
        assert called_url.endswith("/register")

    @patch("OdooDevMCP.services.phone_home.requests.post")
    def test_skips_when_no_url_configured(self, mock_post, mock_env):
        """Should return False when phone_home_url is not set."""
        mock_env._icp_store["mcp.phone_home_url"] = ""

        result = register_server(mock_env)

        assert result is False
        mock_post.assert_not_called()

    @patch("OdooDevMCP.services.phone_home.requests.post")
    def test_skips_when_url_is_false(self, mock_post, mock_env):
        """ICP returns False (Odoo falsy) when param is not set."""
        mock_env._icp_store.pop("mcp.phone_home_url", None)
        # get_param will return default=False

        result = register_server(mock_env)

        assert result is False
        mock_post.assert_not_called()

    @patch("time.sleep")
    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_retries_on_failure(self, mock_network, mock_post, mock_sleep, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_retry_count"] = "3"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
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

        result = register_server(mock_env)

        assert result is True
        assert mock_post.call_count == 3

    @patch("time.sleep")
    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_returns_false_after_all_retries_fail(self, mock_network, mock_post, mock_sleep, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_retry_count"] = "2"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
            "hostname": "test",
            "primary": "127.0.0.1",
            "all": ["127.0.0.1"],
        }

        mock_post.side_effect = Exception("Connection error")

        result = register_server(mock_env)

        assert result is False
        assert mock_post.call_count == 2


# ---------------------------------------------------------------------------
# send_heartbeat
# ---------------------------------------------------------------------------

class TestSendHeartbeat:

    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_sends_heartbeat(self, mock_network, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_heartbeat(mock_env)

        assert result is True
        mock_post.assert_called_once()

        # Verify payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["server_id"] == "test_db_test-server"
        assert payload["status"] == "healthy"

        # URL should have /heartbeat appended
        called_url = mock_post.call_args[0][0]
        assert called_url.endswith("/heartbeat")

    @patch("OdooDevMCP.services.phone_home.requests.post")
    def test_returns_false_when_no_url(self, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = ""

        result = send_heartbeat(mock_env)

        assert result is False
        mock_post.assert_not_called()

    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_returns_false_on_http_error(self, mock_network, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
            "hostname": "test",
            "primary": "127.0.0.1",
            "all": ["127.0.0.1"],
        }

        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = send_heartbeat(mock_env)

        assert result is False

    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_returns_false_on_exception(self, mock_network, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
            "hostname": "test",
            "primary": "127.0.0.1",
            "all": ["127.0.0.1"],
        }

        mock_post.side_effect = Exception("Network error")

        result = send_heartbeat(mock_env)

        assert result is False


# ---------------------------------------------------------------------------
# get_server_hostname
# ---------------------------------------------------------------------------

class TestGetServerHostname:

    @patch("OdooDevMCP.services.phone_home.socket")
    def test_returns_current_hostname(self, mock_socket):
        mock_socket.gethostname.return_value = "test-server-123"

        result = get_server_hostname()

        assert result == "test-server-123"
        mock_socket.gethostname.assert_called_once()


# ---------------------------------------------------------------------------
# _build_server_payload
# ---------------------------------------------------------------------------

class TestBuildServerPayload:

    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_returns_all_required_fields(self, mock_network, mock_env):
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        payload = _build_server_payload(mock_env)

        # Verify all required fields are present
        assert "server_id" in payload
        assert "hostname" in payload
        assert "ip_addresses" in payload
        assert "port" in payload
        assert "transport" in payload
        assert "version" in payload
        assert "odoo_version" in payload
        assert "database" in payload
        assert "capabilities" in payload
        assert "odoo_stage" in payload

        # Verify specific values
        assert payload["server_id"] == "test_db_test-server"
        assert payload["hostname"] == "test-server"
        assert payload["port"] == 8768
        assert payload["transport"] == "http/sse"
        assert payload["version"] == "1.0.0"
        assert payload["database"] == "test_db"
        assert isinstance(payload["capabilities"], list)

    @patch.dict("os.environ", {"ODOO_STAGE": "production"})
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_includes_odoo_stage_from_env(self, mock_network, mock_env):
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        payload = _build_server_payload(mock_env)

        assert payload["odoo_stage"] == "production"

    @patch.dict("os.environ", {}, clear=True)
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_odoo_stage_empty_when_not_set(self, mock_network, mock_env):
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        payload = _build_server_payload(mock_env)

        assert payload["odoo_stage"] == ""

    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_capabilities_are_dynamic(self, mock_network, mock_env):
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        payload = _build_server_payload(mock_env)

        # Capabilities should be a non-empty list from the tool registry
        assert isinstance(payload["capabilities"], list)
        assert len(payload["capabilities"]) > 0


# ---------------------------------------------------------------------------
# enriched heartbeat
# ---------------------------------------------------------------------------

class TestEnrichedHeartbeat:

    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_enriched_heartbeat_includes_full_server_info(self, mock_network, mock_post, mock_env):
        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"
        mock_env._icp_store["mcp.server_port"] = "8768"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_heartbeat(mock_env)

        assert result is True
        mock_post.assert_called_once()

        # Verify enriched payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]

        # Heartbeat-specific fields
        assert payload["status"] == "healthy"
        assert "timestamp" in payload
        assert "uptime_seconds" in payload

        # Full server info from _build_server_payload
        assert payload["server_id"] == "test_db_test-server"
        assert payload["hostname"] == "test-server"
        assert payload["database"] == "test_db"
        assert payload["port"] == 8768
        assert payload["transport"] == "http/sse"
        assert payload["version"] == "1.0.0"
        assert "odoo_version" in payload
        assert "capabilities" in payload
        assert "odoo_stage" in payload

    @patch("OdooDevMCP.services.phone_home.time")
    @patch("OdooDevMCP.services.phone_home.requests.post")
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_uptime_seconds_is_calculated(self, mock_network, mock_post, mock_time, mock_env):
        # Mock the module-level _server_start_time
        import OdooDevMCP.services.phone_home as phone_home_module
        original_start_time = phone_home_module._server_start_time

        # Set start time to 1000
        phone_home_module._server_start_time = 1000.0
        # Current time is 1300
        mock_time.time.return_value = 1300.0

        mock_env._icp_store["mcp.phone_home_url"] = "http://registry.example.com"
        mock_env._icp_store["mcp.phone_home_timeout"] = "5"

        mock_network.return_value = {
            "hostname": "test-server",
            "primary": "192.168.1.100",
            "all": ["192.168.1.100"],
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_heartbeat(mock_env)

        assert result is True

        # Verify uptime_seconds
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["uptime_seconds"] == 300.0

        # Restore original start time
        phone_home_module._server_start_time = original_start_time
