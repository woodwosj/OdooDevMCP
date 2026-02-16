# -*- coding: utf-8 -*-
"""Database query and manipulation tools using Odoo's cursor."""

import logging
import time
from typing import List, Optional

_logger = logging.getLogger(__name__)


def query_database(
    env,
    query: str,
    params: Optional[List] = None,
    limit: int = 1000,
) -> dict:
    """Execute a read-only SQL query against the Odoo PostgreSQL database.

    Args:
        env: Odoo environment
        query: SQL query to execute (SELECT or other read-only statement)
        params: Parameterized query values (positional)
        limit: Maximum number of rows to return

    Returns:
        dict: columns, rows, row_count, truncated, duration_ms
    """
    from ..security.security import audit_log, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'query', max_calls=100, period=60)

    # Get configuration
    ICP = env['ir.config_parameter'].sudo()
    max_result_rows = int(ICP.get_param('mcp.max_result_rows', default=1000))

    start_time = time.time()

    # Validate limit
    if limit > max_result_rows:
        limit = max_result_rows

    try:
        cr = env.cr

        # Apply limit if not in query
        final_query = query
        final_params = list(params) if params else []

        if limit and "LIMIT" not in query.upper():
            final_query = f"{query} LIMIT %s"
            final_params.append(limit)

        # Execute query with parameters
        if final_params:
            cr.execute(final_query, final_params)
        else:
            cr.execute(final_query)

        # Get column names
        columns = [desc[0] for desc in cr.description] if cr.description else []

        # Fetch results
        rows = cr.fetchall()

        # Convert to list of dicts
        result_rows = []
        for row in rows:
            result_rows.append(dict(zip(columns, row)))

        # Check if truncated
        truncated = False
        if limit and len(result_rows) >= limit:
            truncated = True

        duration_ms = int((time.time() - start_time) * 1000)

        # Audit log
        audit_log(
            env,
            tool="query_database",
            query=query[:100],  # Truncate long queries
            rows=len(result_rows),
            duration_ms=duration_ms,
        )

        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "truncated": truncated,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _logger.error(f"Query failed: {e}")

        audit_log(
            env,
            tool="query_database",
            query=query[:100],
            error=str(e),
            duration_ms=duration_ms,
        )

        raise


def execute_sql(
    env,
    statement: str,
    params: Optional[List] = None,
) -> dict:
    """Execute a write SQL statement against the Odoo PostgreSQL database.

    Args:
        env: Odoo environment
        statement: SQL statement to execute (INSERT, UPDATE, DELETE, DDL)
        params: Parameterized query values (positional)

    Returns:
        dict: affected_rows, status_message, duration_ms
    """
    from ..security.security import audit_log, check_rate_limit

    # Check rate limit
    check_rate_limit(env, 'write', max_calls=50, period=60)

    start_time = time.time()

    try:
        cr = env.cr

        # Execute statement with parameters
        if params:
            cr.execute(statement, params)
        else:
            cr.execute(statement)

        # Commit is handled by Odoo's transaction manager
        # Get affected rows
        affected_rows = cr.rowcount

        duration_ms = int((time.time() - start_time) * 1000)

        # Audit log (includes full statement for write operations)
        audit_log(
            env,
            tool="execute_sql",
            statement=statement[:200],  # Truncate very long statements
            affected_rows=affected_rows,
            duration_ms=duration_ms,
        )

        return {
            "affected_rows": affected_rows,
            "status_message": f"OK {affected_rows}",
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        _logger.error(f"Statement execution failed: {e}")

        audit_log(
            env,
            tool="execute_sql",
            statement=statement[:200],
            error=str(e),
            duration_ms=duration_ms,
        )

        raise


def get_db_schema(
    env,
    action: str,
    table_name: Optional[str] = None,
    schema_name: str = "public",
) -> dict:
    """Retrieve database schema information.

    Args:
        env: Odoo environment
        action: What schema info to retrieve (list_tables, describe_table, list_indexes, list_constraints)
        table_name: Table name (required for describe_table, list_indexes, list_constraints)
        schema_name: PostgreSQL schema (defaults to 'public')

    Returns:
        dict: Schema information based on action
    """
    from ..security.security import audit_log

    start_time = time.time()

    try:
        if action == "list_tables":
            result = _list_tables(env, schema_name)
        elif action == "describe_table":
            if not table_name:
                raise ValueError("table_name required for describe_table action")
            result = _describe_table(env, table_name, schema_name)
        elif action == "list_indexes":
            if not table_name:
                raise ValueError("table_name required for list_indexes action")
            result = _list_indexes(env, table_name, schema_name)
        elif action == "list_constraints":
            if not table_name:
                raise ValueError("table_name required for list_constraints action")
            result = _list_constraints(env, table_name, schema_name)
        else:
            raise ValueError(f"Unknown action: {action}")

        duration_ms = int((time.time() - start_time) * 1000)

        # Audit log
        audit_log(
            env,
            tool="get_db_schema",
            action=action,
            table=table_name or "all",
            duration_ms=duration_ms,
        )

        return result

    except Exception as e:
        _logger.error(f"Schema retrieval failed: {e}")
        raise


def _list_tables(env, schema_name: str) -> dict:
    """List all tables in the schema."""
    query = """
        SELECT
            t.tablename AS table_name,
            pg_class.reltuples::bigint AS row_estimate,
            pg_total_relation_size(quote_ident(t.tablename)::regclass) AS size_bytes
        FROM pg_tables t
        JOIN pg_class ON pg_class.relname = t.tablename
        WHERE t.schemaname = %s
        ORDER BY t.tablename
    """

    cr = env.cr
    cr.execute(query, [schema_name])
    rows = cr.dictfetchall()

    return {"tables": rows, "table_count": len(rows)}


def _describe_table(env, table_name: str, schema_name: str) -> dict:
    """Describe a table's columns and types."""
    query = """
        SELECT
            column_name AS name,
            data_type AS type,
            is_nullable = 'YES' AS nullable,
            column_default AS default,
            EXISTS(
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = %s
                    AND tc.table_name = %s
                    AND kcu.column_name = c.column_name
                    AND tc.constraint_type = 'PRIMARY KEY'
            ) AS is_primary_key
        FROM information_schema.columns c
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """

    cr = env.cr
    cr.execute(query, [schema_name, table_name, schema_name, table_name])
    rows = cr.dictfetchall()

    return {
        "table_name": table_name,
        "columns": rows,
        "column_count": len(rows),
    }


def _list_indexes(env, table_name: str, schema_name: str) -> dict:
    """List indexes for a table."""
    query = """
        SELECT
            i.relname AS name,
            array_agg(a.attname ORDER BY a.attnum) AS columns,
            ix.indisunique AS unique,
            am.amname AS type
        FROM pg_class t
        JOIN pg_index ix ON t.oid = ix.indrelid
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_am am ON i.relam = am.oid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = %s AND t.relname = %s
        GROUP BY i.relname, ix.indisunique, am.amname
        ORDER BY i.relname
    """

    cr = env.cr
    cr.execute(query, [schema_name, table_name])
    rows = cr.dictfetchall()

    return {"table_name": table_name, "indexes": rows}


def _list_constraints(env, table_name: str, schema_name: str) -> dict:
    """List constraints for a table."""
    query = """
        SELECT
            tc.constraint_name AS name,
            tc.constraint_type AS type,
            array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS columns,
            pg_get_constraintdef(c.oid) AS definition
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN pg_constraint c ON c.conname = tc.constraint_name
        WHERE tc.table_schema = %s AND tc.table_name = %s
        GROUP BY tc.constraint_name, tc.constraint_type, c.oid
        ORDER BY tc.constraint_type, tc.constraint_name
    """

    cr = env.cr
    cr.execute(query, [schema_name, table_name])
    rows = cr.dictfetchall()

    return {"table_name": table_name, "constraints": rows}
