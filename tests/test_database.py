"""Tests for database tools using Odoo's env.cr cursor."""

from unittest.mock import MagicMock, Mock, patch, call

import pytest

from OdooDevMCP.tools.database import execute_sql, get_db_schema, query_database


# ---------------------------------------------------------------------------
# query_database
# ---------------------------------------------------------------------------

class TestQueryDatabase:

    def test_executes_simple_query(self, mock_env):
        """Should execute a query and return dict-format rows."""
        mock_env.cr.description = [("id",), ("name",)]
        mock_env.cr.fetchall.return_value = [(1, "Alice"), (2, "Bob")]

        result = query_database(mock_env, "SELECT id, name FROM users")

        assert result["columns"] == ["id", "name"]
        assert result["row_count"] == 2
        assert result["rows"][0] == {"id": 1, "name": "Alice"}
        assert result["rows"][1] == {"id": 2, "name": "Bob"}
        assert "duration_ms" in result

    def test_applies_limit_when_not_in_query(self, mock_env):
        """Should append LIMIT %s when query has no LIMIT clause."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = [(1,)]

        query_database(mock_env, "SELECT id FROM users", limit=50)

        # Check that execute was called with LIMIT appended
        call_args = mock_env.cr.execute.call_args
        executed_query = call_args[0][0]
        executed_params = call_args[0][1]

        assert "LIMIT %s" in executed_query
        assert 50 in executed_params

    def test_preserves_existing_params_with_limit(self, mock_env):
        """LIMIT should be appended to existing params."""
        mock_env.cr.description = [("id",), ("name",)]
        mock_env.cr.fetchall.return_value = [(1, "Alice")]

        query_database(
            mock_env,
            "SELECT * FROM users WHERE name = %s",
            params=["Alice"],
            limit=10,
        )

        call_args = mock_env.cr.execute.call_args
        executed_params = call_args[0][1]

        assert len(executed_params) == 2
        assert executed_params[0] == "Alice"
        assert executed_params[1] == 10

    def test_does_not_add_limit_when_already_present(self, mock_env):
        """Should not add LIMIT when query already has one."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = [(1,)]

        query_database(mock_env, "SELECT id FROM users LIMIT 5")

        call_args = mock_env.cr.execute.call_args
        executed_query = call_args[0][0]
        # Should only have the original LIMIT 5, not an extra LIMIT %s
        assert executed_query.count("LIMIT") == 1

    def test_clamps_limit_to_max_result_rows(self, mock_env):
        """Requested limit should be clamped to mcp.max_result_rows."""
        mock_env._icp_store["mcp.max_result_rows"] = "100"
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = []

        query_database(mock_env, "SELECT id FROM users", limit=5000)

        call_args = mock_env.cr.execute.call_args
        executed_params = call_args[0][1]
        # Should be clamped to 100
        assert executed_params[-1] == 100

    def test_truncated_flag(self, mock_env):
        """truncated should be True when result count equals limit."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = [(i,) for i in range(5)]

        result = query_database(mock_env, "SELECT id FROM users LIMIT 5", limit=5)

        assert result["row_count"] == 5
        assert result["truncated"] is True

    def test_empty_result(self, mock_env):
        """Should handle empty results gracefully."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = []

        result = query_database(mock_env, "SELECT id FROM users WHERE 1=0")

        assert result["columns"] == ["id"]
        assert result["rows"] == []
        assert result["row_count"] == 0
        assert result["truncated"] is False

    def test_raises_on_execution_error(self, mock_env):
        """Should re-raise database errors."""
        mock_env.cr.execute.side_effect = Exception("syntax error")

        with pytest.raises(Exception, match="syntax error"):
            query_database(mock_env, "INVALID SQL")

    def test_enforces_rate_limit(self, mock_env):
        """After 100 calls, rate limit should kick in."""
        mock_env.cr.description = [("id",)]
        mock_env.cr.fetchall.return_value = []

        for _ in range(100):
            query_database(mock_env, "SELECT 1")

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            query_database(mock_env, "SELECT 1")


# ---------------------------------------------------------------------------
# execute_sql
# ---------------------------------------------------------------------------

class TestExecuteSql:

    def test_executes_statement(self, mock_env):
        mock_env.cr.rowcount = 5

        result = execute_sql(mock_env, "UPDATE users SET active = true WHERE id = %s", params=[1])

        mock_env.cr.execute.assert_called_once()
        assert result["affected_rows"] == 5
        assert result["status_message"] == "OK 5"
        assert "duration_ms" in result

    def test_executes_without_params(self, mock_env):
        mock_env.cr.rowcount = 0

        result = execute_sql(mock_env, "DELETE FROM temp_table")

        mock_env.cr.execute.assert_called_once_with("DELETE FROM temp_table")
        assert result["affected_rows"] == 0

    def test_raises_on_execution_error(self, mock_env):
        mock_env.cr.execute.side_effect = Exception("DB Error")

        with pytest.raises(Exception, match="DB Error"):
            execute_sql(mock_env, "INVALID SQL")


# ---------------------------------------------------------------------------
# get_db_schema
# ---------------------------------------------------------------------------

class TestGetDbSchema:

    def test_list_tables(self, mock_env):
        mock_env.cr.dictfetchall.return_value = [
            {"table_name": "users", "row_estimate": 100, "size_bytes": 8192},
        ]

        result = get_db_schema(mock_env, action="list_tables")

        assert "tables" in result
        assert result["table_count"] == 1
        assert result["tables"][0]["table_name"] == "users"

    def test_describe_table(self, mock_env):
        mock_env.cr.dictfetchall.return_value = [
            {"name": "id", "type": "integer", "nullable": False, "default": None, "is_primary_key": True},
        ]

        result = get_db_schema(mock_env, action="describe_table", table_name="users")

        assert result["table_name"] == "users"
        assert result["column_count"] == 1

    def test_describe_table_requires_table_name(self, mock_env):
        with pytest.raises(ValueError, match="table_name required"):
            get_db_schema(mock_env, action="describe_table")

    def test_unknown_action_raises(self, mock_env):
        with pytest.raises(ValueError, match="Unknown action"):
            get_db_schema(mock_env, action="invalid_action")

    def test_list_indexes(self, mock_env):
        mock_env.cr.dictfetchall.return_value = []

        result = get_db_schema(mock_env, action="list_indexes", table_name="users")

        assert result["table_name"] == "users"
        assert "indexes" in result

    def test_list_constraints(self, mock_env):
        mock_env.cr.dictfetchall.return_value = []

        result = get_db_schema(mock_env, action="list_constraints", table_name="users")

        assert result["table_name"] == "users"
        assert "constraints" in result
