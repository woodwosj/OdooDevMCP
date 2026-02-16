"""Tests for the tool registry (get_tool_registry, get_tool_schemas, call_tool)."""

from unittest.mock import MagicMock, patch

import pytest

from OdooDevMCP.tools.registry import call_tool, get_tool_registry, get_tool_schemas


class TestGetToolRegistry:

    def test_returns_dict_of_callables(self):
        registry = get_tool_registry()
        assert isinstance(registry, dict)
        assert len(registry) > 0
        for name, handler in registry.items():
            assert callable(handler), f"Tool '{name}' handler is not callable"

    def test_contains_expected_tools(self):
        registry = get_tool_registry()
        expected = [
            "execute_command",
            "query_database",
            "execute_sql",
            "get_db_schema",
            "read_file",
            "write_file",
            "odoo_shell",
            "service_status",
            "read_config",
            "list_modules",
            "get_module_info",
            "install_module",
            "upgrade_module",
            "register_receiver",
        ]
        for tool_name in expected:
            assert tool_name in registry, f"Missing tool: {tool_name}"


class TestGetToolSchemas:

    def test_returns_dict_of_schemas(self):
        schemas = get_tool_schemas()
        assert isinstance(schemas, dict)
        assert len(schemas) > 0

    def test_schemas_have_description_and_parameters(self):
        schemas = get_tool_schemas()
        for name, schema in schemas.items():
            assert "description" in schema, f"Schema '{name}' missing 'description'"
            assert "parameters" in schema, f"Schema '{name}' missing 'parameters'"

    def test_schemas_match_registry_tools(self):
        """Every registered tool should have a schema, and vice versa."""
        registry = get_tool_registry()
        schemas = get_tool_schemas()

        registry_names = set(registry.keys())
        schema_names = set(schemas.keys())

        assert registry_names == schema_names, (
            f"Mismatch between registry and schemas. "
            f"In registry only: {registry_names - schema_names}. "
            f"In schemas only: {schema_names - registry_names}."
        )


class TestCallTool:

    def test_dispatches_to_correct_handler(self, mock_env):
        """call_tool should invoke the handler with env + parameters."""
        with patch("OdooDevMCP.tools.terminal.subprocess.run") as mock_run:
            from unittest.mock import Mock
            mock_run.return_value = Mock(returncode=0, stdout="dispatched", stderr="")

            result = call_tool(mock_env, "execute_command", {"command": "echo hello"})

            assert result["stdout"] == "dispatched"

    def test_raises_on_unknown_tool(self, mock_env):
        with pytest.raises(ValueError, match="Unknown tool"):
            call_tool(mock_env, "nonexistent_tool", {})

    def test_passes_parameters_as_kwargs(self, mock_env):
        """Parameters dict should be unpacked as keyword arguments."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = []

        result = call_tool(mock_env, "query_database", {"query": "SELECT 1", "limit": 10})

        assert result["row_count"] == 0
