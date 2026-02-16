"""Tests for database utilities."""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from odoo_dev_mcp.utils.db import execute_query, execute_statement, get_db_pool


class TestGetDbPool:
    """Test database pool initialization."""

    @patch("odoo_dev_mcp.utils.db.pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_creates_pool_on_first_call(self, mock_get_config, mock_pool_module, mock_config):
        """Pool should be created on first call."""
        # Reset the global pool
        import odoo_dev_mcp.utils.db as db_module

        db_module._db_pool = None

        mock_get_config.return_value = mock_config
        mock_pool_instance = MagicMock()
        mock_pool_module.SimpleConnectionPool.return_value = mock_pool_instance

        result = get_db_pool()

        assert result == mock_pool_instance
        mock_pool_module.SimpleConnectionPool.assert_called_once()

    @patch("odoo_dev_mcp.utils.db.pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_returns_existing_pool(self, mock_get_config, mock_pool_module, mock_config):
        """Should return existing pool without creating a new one."""
        import odoo_dev_mcp.utils.db as db_module

        # Set up existing pool
        existing_pool = MagicMock()
        db_module._db_pool = existing_pool

        mock_get_config.return_value = mock_config

        result = get_db_pool()

        # Should return existing pool
        assert result == existing_pool
        # Should not create a new pool
        mock_pool_module.SimpleConnectionPool.assert_not_called()

    @patch("odoo_dev_mcp.utils.db.pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_thread_safe_initialization(self, mock_get_config, mock_pool_module, mock_config):
        """Pool initialization should be thread-safe (C4 fix)."""
        import odoo_dev_mcp.utils.db as db_module

        db_module._db_pool = None

        mock_get_config.return_value = mock_config
        mock_pool_instance = MagicMock()
        mock_pool_module.SimpleConnectionPool.return_value = mock_pool_instance

        results = []

        def create_pool():
            results.append(get_db_pool())

        # Create multiple threads trying to get pool simultaneously
        threads = [threading.Thread(target=create_pool) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Pool should only be created once
        assert mock_pool_module.SimpleConnectionPool.call_count == 1
        # All threads should get the same pool instance
        assert all(r == mock_pool_instance for r in results)


class TestExecuteQuery:
    """Test query execution with parameterization."""

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_executes_query_with_params(self, mock_get_config, mock_get_pool, mock_config):
        """Query should be executed with parameters."""
        mock_get_config.return_value = mock_config

        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.description = [("id",), ("name",)]
        cursor.fetchall.return_value = [(1, "Test")]

        result = execute_query("SELECT * FROM users WHERE id = %s", params=[1])

        cursor.execute.assert_called()
        assert result["row_count"] == 1
        assert result["rows"][0]["id"] == 1
        assert result["rows"][0]["name"] == "Test"

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_applies_limit_with_parameterization(
        self, mock_get_config, mock_get_pool, mock_config
    ):
        """LIMIT should be applied using parameterized query (C1 fix)."""
        mock_get_config.return_value = mock_config

        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.description = [("id",)]
        cursor.fetchall.return_value = [(1,), (2,), (3,)]

        result = execute_query("SELECT * FROM users", limit=3)

        # Should use parameterized LIMIT
        call_args = cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1] if len(call_args[0]) > 1 else None

        assert "LIMIT %s" in query
        assert params == [3]

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_preserves_existing_params_with_limit(
        self, mock_get_config, mock_get_pool, mock_config
    ):
        """LIMIT should be appended to existing params (C1 fix)."""
        mock_get_config.return_value = mock_config

        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.description = [("id",), ("name",)]
        cursor.fetchall.return_value = [(1, "Test")]

        result = execute_query(
            "SELECT * FROM users WHERE name = %s", params=["Test"], limit=10
        )

        call_args = cursor.execute.call_args
        params = call_args[0][1]

        # Should have both original param and limit
        assert len(params) == 2
        assert params[0] == "Test"
        assert params[1] == 10

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    @patch("odoo_dev_mcp.utils.db.get_config")
    def test_sets_read_only_transaction(self, mock_get_config, mock_get_pool, mock_config):
        """Should set transaction to read-only mode."""
        mock_get_config.return_value = mock_config

        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.description = [("id",)]
        cursor.fetchall.return_value = []

        execute_query("SELECT 1", read_only=True)

        # Should execute SET TRANSACTION READ ONLY
        calls = [str(call) for call in cursor.execute.call_args_list]
        assert any("READ ONLY" in str(call) for call in calls)

    def _setup_mocks(self, mock_get_pool):
        """Helper to set up database mocks."""
        pool = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()

        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        mock_get_pool.return_value = pool

        return pool, conn, cursor


class TestExecuteStatement:
    """Test write statement execution."""

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    def test_executes_statement_and_commits(self, mock_get_pool):
        """Statement should be executed and committed."""
        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.rowcount = 5
        cursor.statusmessage = "UPDATE 5"

        result = execute_statement("UPDATE users SET active = true WHERE id = %s", params=[1])

        cursor.execute.assert_called_once()
        conn.commit.assert_called_once()
        assert result["affected_rows"] == 5
        assert result["status_message"] == "UPDATE 5"

    @patch("odoo_dev_mcp.utils.db.get_db_pool")
    def test_rolls_back_on_error(self, mock_get_pool):
        """Should rollback on error."""
        pool, conn, cursor = self._setup_mocks(mock_get_pool)
        cursor.execute.side_effect = Exception("DB Error")

        with pytest.raises(Exception, match="DB Error"):
            execute_statement("INVALID SQL")

        conn.rollback.assert_called_once()

    def _setup_mocks(self, mock_get_pool):
        """Helper to set up database mocks."""
        pool = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()

        pool.getconn.return_value = conn
        conn.cursor.return_value = cursor
        mock_get_pool.return_value = pool

        return pool, conn, cursor
