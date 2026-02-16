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
        mock_gethostname.return_value = "new-host-abc123"
        mock_env._icp_store["mcp.last_hostname"] = "old-host-xyz789"
        mock_register.return_value = True

        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        controller = MCPController()

        # Build mock registry + cursor that returns our mock_env's ICP
        mock_icp = MagicMock()
        mock_icp.get_param.side_effect = lambda key, default='': mock_env._icp_store.get(key, default)
        mock_icp.set_param.side_effect = lambda key, val: mock_env._icp_store.__setitem__(key, val)

        mock_cursor = MagicMock()
        mock_registry = MagicMock()
        mock_registry.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_registry.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_odoo_env = MagicMock()
        mock_odoo_env.__getitem__ = Mock(return_value=mock_icp)

        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls, \
             patch("odoo.modules.registry.Registry", return_value=mock_registry), \
             patch("odoo.api.Environment", return_value=mock_odoo_env):
            mock_request.db = "testdb"

            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            response = controller.health_check()

            assert response.status_code == 200
            mock_thread.assert_called_once()
            thread_kwargs = mock_thread.call_args[1]
            assert thread_kwargs['daemon'] is True

    @patch("threading.Thread")
    @patch("socket.gethostname")
    def test_no_hostname_change_skips_registration(self, mock_gethostname, mock_thread):
        """When hostname matches, health endpoint should not trigger registration."""
        current_hostname = "same-host-123"
        mock_gethostname.return_value = current_hostname

        mock_icp = MagicMock()
        mock_icp.get_param.return_value = current_hostname

        mock_cursor = MagicMock()
        mock_registry = MagicMock()
        mock_registry.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_registry.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_odoo_env = MagicMock()
        mock_odoo_env.__getitem__ = Mock(return_value=mock_icp)

        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        controller = MCPController()

        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls, \
             patch("odoo.modules.registry.Registry", return_value=mock_registry), \
             patch("odoo.api.Environment", return_value=mock_odoo_env):
            mock_request.db = "testdb"

            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            response = controller.health_check()

            assert response.status_code == 200
            mock_thread.assert_not_called()

    @patch("threading.Thread")
    @patch("socket.gethostname")
    def test_first_request_initializes_last_hostname(self, mock_gethostname, mock_thread, mock_env):
        """First request with no last_hostname should trigger registration."""
        mock_gethostname.return_value = "first-host-123"
        if "mcp.last_hostname" in mock_env._icp_store:
            del mock_env._icp_store["mcp.last_hostname"]

        mock_icp = MagicMock()
        mock_icp.get_param.side_effect = lambda key, default='': mock_env._icp_store.get(key, default)
        mock_icp.set_param.side_effect = lambda key, val: mock_env._icp_store.__setitem__(key, val)

        mock_cursor = MagicMock()
        mock_registry = MagicMock()
        mock_registry.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_registry.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_odoo_env = MagicMock()
        mock_odoo_env.__getitem__ = Mock(return_value=mock_icp)

        from OdooDevMCP.controllers.mcp_endpoint import MCPController

        controller = MCPController()

        with patch("OdooDevMCP.controllers.mcp_endpoint.request") as mock_request, \
             patch("OdooDevMCP.controllers.mcp_endpoint.Response") as mock_response_cls, \
             patch("odoo.modules.registry.Registry", return_value=mock_registry), \
             patch("odoo.api.Environment", return_value=mock_odoo_env):
            mock_request.db = "testdb"

            mock_response_instance = Mock()
            mock_response_instance.status_code = 200
            mock_response_cls.return_value = mock_response_instance

            response = controller.health_check()

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
        mock_gethostname.return_value = "new-host-abc123"
        mock_env._icp_store["mcp.last_hostname"] = "old-host-xyz789"
        mock_register.return_value = True
        mock_heartbeat.return_value = True

        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        result = heartbeat_model._cron_send_heartbeat()

        mock_register.assert_called_once_with(mock_env)
        mock_heartbeat.assert_called_once_with(mock_env)
        assert mock_env._icp_store["mcp.last_hostname"] == "new-host-abc123"
        assert result is True

    @patch("OdooDevMCP.services.phone_home.send_heartbeat")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_cron_no_hostname_change(self, mock_gethostname, mock_register, mock_heartbeat, mock_env):
        """Cron should only call send_heartbeat when hostname matches."""
        current_hostname = "same-host-123"
        mock_gethostname.return_value = current_hostname
        mock_env._icp_store["mcp.last_hostname"] = current_hostname
        mock_heartbeat.return_value = True

        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        result = heartbeat_model._cron_send_heartbeat()

        mock_register.assert_not_called()
        mock_heartbeat.assert_called_once_with(mock_env)
        assert result is True

    @patch("OdooDevMCP.services.phone_home.send_heartbeat")
    @patch("OdooDevMCP.services.phone_home.register_server")
    @patch("socket.gethostname")
    def test_cron_calls_register_before_heartbeat(self, mock_gethostname, mock_register, mock_heartbeat, mock_env):
        """When hostname changes, register_server must be called before send_heartbeat."""
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

        from OdooDevMCP.models.mcp_heartbeat import MCPHeartbeat

        heartbeat_model = MCPHeartbeat()
        heartbeat_model.env = mock_env

        heartbeat_model._cron_send_heartbeat()

        assert call_order == ['register', 'heartbeat']
