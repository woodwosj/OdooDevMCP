"""Tests for the register_receiver tool."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from OdooDevMCP.tools.receiver import register_receiver


class TestRegisterReceiver:

    @patch("OdooDevMCP.services.phone_home.register_server", return_value=True)
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_registers_and_stores_url(self, mock_network, mock_register, mock_env):
        mock_network.return_value = {
            "hostname": "test-host",
            "primary": "192.168.1.1",
            "all": ["192.168.1.1"],
        }

        result = register_receiver(mock_env, "https://abc123.ngrok.io")

        assert result["success"] is True
        assert result["url_stored"] == "https://abc123.ngrok.io"
        assert result["registration_sent"] is True
        assert "server_id" in result
        assert "heartbeat_schedule" in result

        # Verify ICP was called to store the URL
        mock_env._icp_sudo.set_param.assert_called()

    @patch("OdooDevMCP.services.phone_home.register_server", return_value=True)
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_strips_register_suffix(self, mock_network, mock_register, mock_env):
        """URL with /register suffix should be normalized to base URL."""
        mock_network.return_value = {
            "hostname": "test-host",
            "primary": "192.168.1.1",
            "all": ["192.168.1.1"],
        }

        result = register_receiver(mock_env, "https://abc123.ngrok.io/register")

        assert result["url_stored"] == "https://abc123.ngrok.io"

    @patch("OdooDevMCP.services.phone_home.register_server", return_value=True)
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_strips_trailing_slash(self, mock_network, mock_register, mock_env):
        mock_network.return_value = {
            "hostname": "test-host",
            "primary": "192.168.1.1",
            "all": ["192.168.1.1"],
        }

        result = register_receiver(mock_env, "https://abc123.ngrok.io/")

        assert result["url_stored"] == "https://abc123.ngrok.io"

    def test_rejects_non_http_url(self, mock_env):
        with pytest.raises(ValueError, match="must start with http"):
            register_receiver(mock_env, "ftp://example.com")

    def test_rejects_empty_url(self, mock_env):
        with pytest.raises(ValueError, match="receiver_url is required"):
            register_receiver(mock_env, "")

    def test_rejects_none_url(self, mock_env):
        with pytest.raises(ValueError, match="receiver_url is required"):
            register_receiver(mock_env, None)

    def test_enforces_rate_limit(self, mock_env):
        """After 5 calls, rate limit should kick in."""
        with patch("OdooDevMCP.services.phone_home.register_server", return_value=True), \
             patch("OdooDevMCP.services.phone_home.get_network_info", return_value={
                 "hostname": "test", "primary": "127.0.0.1", "all": ["127.0.0.1"]
             }):
            for _ in range(5):
                register_receiver(mock_env, "https://example.com")

            with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                register_receiver(mock_env, "https://example.com")

    @patch("OdooDevMCP.services.phone_home.register_server", return_value=False)
    @patch("OdooDevMCP.services.phone_home.get_network_info")
    def test_reports_registration_failure(self, mock_network, mock_register, mock_env):
        """Should still succeed but report registration_sent=False."""
        mock_network.return_value = {
            "hostname": "test-host",
            "primary": "192.168.1.1",
            "all": ["192.168.1.1"],
        }

        result = register_receiver(mock_env, "https://example.com")

        assert result["success"] is True
        assert result["registration_sent"] is False
