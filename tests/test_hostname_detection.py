"""Tests for hostname change detection in health endpoint and cron."""

from unittest.mock import MagicMock, Mock, patch, call
import pytest


class TestHealthEndpointHostnameDetection:
    """Tests for hostname change detection in the health endpoint."""

    @patch("threading.Thread")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_hostname_change_triggers_registration(self, mock_gethostname, mock_register, mock_thread, mock_env):
        """When hostname changes, health endpoint should trigger registration."""
        # Set up mocks
        mock_gethostname.return_value = "new-host-abc123"
        mock_env._icp_store["mcp.last_hostname"] = "old-host-xyz789"
        mock_register.return_value = True

        # Import and call health endpoint logic
        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        # Create controller
        controller = MCPController()

        # Mock the request object and Response
        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls:
            mock_request.env.sudo.return_value = mock_env

            # Mock Response instance
            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            # Call health_check
            response = controller.health_check()

            # Verify response is still healthy
            assert response.status_code == 200

            # Verify thread was started for background registration
            mock_thread.assert_called_once()
            thread_kwargs = mock_thread.call_args[1]
            assert thread_kwargs['daemon'] is True

    @patch("threading.Thread")
    @patch("socket.gethostname")
    def test_no_hostname_change_skips_registration(self, mock_gethostname, mock_thread):
        """When hostname matches, health endpoint should not trigger registration."""
        # Set up mocks
        current_hostname = "same-host-123"
        mock_gethostname.return_value = current_hostname

        # Create a proper mock environment with working ICP
        mock_env = MagicMock()
        icp_store = {"mcp.last_hostname": current_hostname}

        def get_param(key, default=''):
            return icp_store.get(key, default)

        mock_icp = MagicMock()
        mock_icp.get_param.side_effect = get_param
        mock_env.__getitem__.return_value.get_param.side_effect = get_param

        # Import and call health endpoint logic
        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        # Create controller
        controller = MCPController()

        # Mock the request object and Response
        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls:
            mock_request.env.sudo.return_value = mock_env

            # Mock Response instance
            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            # Call health_check
            response = controller.health_check()

            # Verify response is still healthy
            assert response.status_code == 200

            # Verify no thread was started
            mock_thread.assert_not_called()

    @patch("threading.Thread")
    @patch("socket.gethostname")
    def test_first_request_initializes_last_hostname(self, mock_gethostname, mock_thread, mock_env):
        """First request with no last_hostname should trigger registration."""
        # Set up mocks
        mock_gethostname.return_value = "first-host-123"
        # ICP returns empty string when not set
        if "mcp.last_hostname" in mock_env._icp_store:
            del mock_env._icp_store["mcp.last_hostname"]

        # Import and call health endpoint logic
        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        # Create controller
        controller = MCPController()

        # Mock the request object and Response
        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls:
            mock_request.env.sudo.return_value = mock_env

            # Mock Response instance
            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            # Call health_check
            response = controller.health_check()

            # Verify response is still healthy
            assert response.status_code == 200

            # Verify thread was started because empty != current hostname
            mock_thread.assert_called_once()


class TestCronHostnameDetection:
    """Tests for hostname change detection in the heartbeat cron."""

    @patch("OdooDevMCP.services.phone_home.send_heartbeat")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_cron_detects_hostname_change(self, mock_gethostname, mock_register, mock_heartbeat, mock_env):
        """Cron should call register_server before heartbeat when hostname changes."""
        # Set up mocks
        mock_gethostname.return_value = "new-host-abc123"
        mock_env._icp_store["mcp.last_hostname"] = "old-host-xyz789"
        mock_register.return_value = True
        mock_heartbeat.return_value = True

        # Import and call cron
        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        # Create model instance
        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        # Call cron method
        result = heartbeat_model._cron_send_heartbeat()

        # Verify both register_server and send_heartbeat were called
        mock_register.assert_called_once_with(mock_env)
        mock_heartbeat.assert_called_once_with(mock_env)

        # Verify last_hostname was updated
        assert mock_env._icp_store["mcp.last_hostname"] == "new-host-abc123"

        assert result is True

    @patch("OdooDevMCP.services.phone_home.send_heartbeat")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_cron_no_hostname_change(self, mock_gethostname, mock_register, mock_heartbeat, mock_env):
        """Cron should only call send_heartbeat when hostname matches."""
        # Set up mocks
        current_hostname = "same-host-123"
        mock_gethostname.return_value = current_hostname
        mock_env._icp_store["mcp.last_hostname"] = current_hostname
        mock_heartbeat.return_value = True

        # Import and call cron
        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        # Create model instance
        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        # Call cron method
        result = heartbeat_model._cron_send_heartbeat()

        # Verify only send_heartbeat was called, not register_server
        mock_register.assert_not_called()
        mock_heartbeat.assert_called_once_with(mock_env)

        assert result is True

    @patch("OdooDevMCP.services.phone_home.send_heartbeat")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_cron_calls_register_before_heartbeat(self, mock_gethostname, mock_register, mock_heartbeat, mock_env):
        """When hostname changes, register_server must be called before send_heartbeat."""
        # Set up mocks
        mock_gethostname.return_value = "new-host"
        mock_env._icp_store["mcp.last_hostname"] = "old-host"

        call_order = []

        def track_register(env):
            call_order.append('register')
            return True

        def track_heartbeat(env):
            call_order.append('heartbeat')
            return True

        mock_register.side_effect = track_register
        mock_heartbeat.side_effect = track_heartbeat

        # Import and call cron
        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        # Create model instance
        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        # Call cron method
        heartbeat_model._cron_send_heartbeat()

        # Verify call order
        assert call_order == ['register', 'heartbeat']
