# Odoo Dev MCP Server

An Odoo V18 module that provides a Model Context Protocol (MCP) server running **within Odoo**. This gives AI agents direct access to Odoo capabilities including terminal control, database operations via Odoo's cursor, filesystem management, Odoo ORM/shell execution, and service administration.

## Key Features

- **Runs as an Odoo Module**: Installable on Odoo.sh and self-hosted Odoo servers
- **HTTP/SSE Transport**: MCP endpoint at `/mcp/v1` (no stdio dependency)
- **Direct Database Access**: Uses Odoo's `env.cr` cursor for SQL operations
- **Odoo ORM Integration**: Execute Python code with full `env` context
- **Phone-Home Registration**: Automatic server registration on module installation
- **Configuration UI**: Settings accessible via Odoo Settings menu
- **Complete Audit Logging**: All operations logged to audit file

## Architecture

```
+---------------------------+
|     Odoo Server           |
|                           |
|  +---------------------+  |
|  | OdooDevMCP Module   |  |
|  | - HTTP Controller   |  |       +------------------+
|  | - MCP Server        |--------->| Registry API     |
|  | - Tools/Services    |  |  POST | (phone-home)     |
|  +---------------------+  |       +------------------+
|    |   |   |   |          |
|    v   v   v   v          |
|  [PG] [FS] [ORM] [SVC]   |       +------------------+
|                           |       | MCP Client       |
|  +---------------------+  |<------| (Claude, IDE)    |
|  | PostgreSQL          |  |  HTTP +------------------+
|  +---------------------+  | /mcp/v1
|                           |
+---------------------------+
```

## Installation

### Prerequisites

- Odoo 18.0
- Python 3.10+
- psycopg2 (usually already installed with Odoo)
- Additional Python packages: `mcp`, `pyyaml`, `requests`, `pydantic`

### On Odoo.sh

1. Add this module to your `custom-addons` directory
2. Install Python dependencies in `requirements.txt`:
   ```
   mcp>=1.0.0
   pyyaml>=6.0
   requests>=2.28.0
   pydantic>=2.0.0
   ```
3. Push to your Odoo.sh repository
4. Install the module via the Apps menu

### On Self-Hosted Odoo

1. Copy the module directory to your `addons` path:
   ```bash
   cp -r OdooDevMCP /opt/odoo/custom-addons/
   ```

2. Install Python dependencies:
   ```bash
   source /opt/odoo/venv/bin/activate
   pip install mcp pyyaml requests pydantic
   ```

3. Update the apps list and install:
   ```bash
   # Restart Odoo
   sudo systemctl restart odoo

   # Or update module list via CLI
   odoo -d your_database -u all --stop-after-init
   ```

4. Install via Odoo UI:
   - Go to Apps
   - Search for "Odoo Dev MCP Server"
   - Click Install

## Configuration

After installation, configure the module via **Settings > MCP Server > Configuration**:

### Server Settings
- **Server Host**: Bind address (default: `127.0.0.1` for localhost only)
- **Server Port**: HTTP port (default: `8768`)
- **API Key**: Bearer token for authentication (leave empty for no auth during development)
- **Log Level**: Logging verbosity (debug, info, warning, error)

### Phone-Home Settings
- **Phone-Home URL**: API endpoint to register server on startup (optional)
- **Heartbeat Interval**: Seconds between heartbeat pings (default: 60)

### Command Settings
- **Default Command Timeout**: Default timeout in seconds (default: 30)
- **Max Command Timeout**: Maximum allowed timeout (default: 600)

### Filesystem Settings
- **Max Read Size**: Maximum file size for reads in MB (default: 10)
- **Max Write Size**: Maximum file size for writes in MB (default: 50)

### Database Settings
- **Query Timeout**: Default query timeout in seconds (default: 30)
- **Max Result Rows**: Maximum rows returned by queries (default: 1000)

### Audit Settings
- **Audit Logging Enabled**: Enable/disable audit logging
- **Audit Log Path**: Path to audit log file (default: `/var/log/odoo/mcp_audit.log`)

## Usage

### MCP Endpoint

The MCP server exposes a JSON-RPC endpoint at:
```
http://your-odoo-server:8069/mcp/v1
```

Or on the configured port:
```
http://your-odoo-server:8768/mcp/v1
```

### Health Check

```bash
curl http://localhost:8768/mcp/v1/health
```

### Capabilities

```bash
curl http://localhost:8768/mcp/v1/capabilities \
  -H "Authorization: Bearer your-api-key"
```

### MCP Client Configuration

Configure your MCP client (Claude Code, etc.) to connect:

```json
{
  "mcpServers": {
    "odoo-dev": {
      "url": "http://your-odoo-server:8768/mcp/v1",
      "headers": {
        "Authorization": "Bearer your-api-key"
      }
    }
  }
}
```

## Available Tools

The module provides 13 MCP tools:

1. **execute_command** - Run shell commands on the server
2. **query_database** - Execute read-only SQL queries via Odoo cursor
3. **execute_sql** - Execute write SQL statements (INSERT, UPDATE, DELETE, DDL)
4. **get_db_schema** - Inspect database schema (tables, columns, indexes, constraints)
5. **read_file** - Read files from the server filesystem
6. **write_file** - Write files to the server filesystem
7. **odoo_shell** - Execute Python code with full Odoo `env` context
8. **service_status** - Check and manage systemd services (odoo, postgresql, nginx)
9. **read_config** - Read Odoo configuration file
10. **list_modules** - List Odoo modules with installation status
11. **get_module_info** - Get detailed info about a specific module
12. **install_module** - Install an Odoo module
13. **upgrade_module** - Upgrade an installed module

## Available Resources

The module provides 5 MCP resources:

1. **odoo://config** - Current Odoo configuration (sensitive values masked)
2. **odoo://logs/{service}** - Recent service logs
3. **odoo://schema/{table}** - Database table schema
4. **odoo://modules** - List of installed modules
5. **odoo://system** - System information (OS, memory, disk, versions)

## Security

### Trust Model

This is a **development and administration tool**. The trust boundary is at the MCP client level. Anyone who can connect to the MCP endpoint has full access to the server.

**This is NOT a public-facing service.** Only use in trusted environments with proper access controls.

### Authentication

- **API Key**: Configure a Bearer token in Settings > MCP Server Configuration
- Clients must include `Authorization: Bearer <api_key>` header
- Leave API key empty during development (not recommended for production)

### Audit Logging

All tool invocations are logged to the configured audit log path:

```
[2026-02-16T10:05:30Z] DB=production USER=2 TOOL=execute_command CMD="systemctl restart odoo" EXIT_CODE=0 DURATION=1200ms
[2026-02-16T10:05:32Z] DB=production USER=2 TOOL=query_database QUERY="SELECT count(*) FROM res_partner" ROWS=1 DURATION=5ms
```

### Rate Limiting

Built-in rate limiting prevents abuse:
- Commands: 10/minute
- Queries: 100/minute
- Write operations: 50/minute
- Shell execution: 5/minute
- File reads: 50/minute
- File writes: 30/minute

### Path Validation

All filesystem operations validate paths to prevent:
- Path traversal attacks (`..` in paths)
- Symlink exploits (resolved before validation)
- Relative path confusion (absolute paths required)

## Phone-Home Registration

On module installation, the server can register itself with a configured API endpoint:

**Payload sent to `phone_home_url`:**
```json
{
  "server_id": "database_hostname",
  "hostname": "odoo-server-01",
  "ip_addresses": {
    "primary": "10.0.1.50",
    "all": ["10.0.1.50", "172.17.0.1"]
  },
  "port": 8768,
  "transport": "http/sse",
  "version": "1.0.0",
  "odoo_version": "18.0",
  "database": "production",
  "capabilities": [...],
  "started_at": "2026-02-16T10:00:00Z"
}
```

This enables fleet management and discovery of all deployed Odoo MCP servers.

## Monitoring

### Check Module Status

In Odoo: Apps > Search "MCP" > Check installation status

### View Logs

```bash
# Odoo server log (includes MCP module output)
tail -f /var/log/odoo/odoo.log | grep MCP

# Audit log
tail -f /var/log/odoo/mcp_audit.log
```

### Test Endpoint

```bash
# Health check
curl http://localhost:8768/mcp/v1/health

# Capabilities (requires API key if configured)
curl http://localhost:8768/mcp/v1/capabilities \
  -H "Authorization: Bearer your-api-key"
```

## Troubleshooting

### Module won't install

Check logs:
```bash
tail -f /var/log/odoo/odoo.log
```

Common issues:
- Missing Python dependencies (`mcp`, `pyyaml`, `requests`, `pydantic`)
- Python version < 3.10
- Insufficient permissions to create audit log directory

### MCP endpoint returns 404

- Check that Odoo is running
- Verify module is installed (not just "To Install")
- Check server port configuration matches your request URL

### Database operations fail

- Check that the user has database access permissions
- Verify PostgreSQL is running: `systemctl status postgresql`
- Check Odoo's database configuration

### Phone-home not working

- Verify `phone_home_url` is configured in Settings
- Check network connectivity to the registry URL
- Phone-home failures are non-blocking and logged as warnings

## Development

### Module Structure

```
OdooDevMCP/
├── __init__.py                 # Module initialization + post_init_hook
├── __manifest__.py             # Module metadata and dependencies
├── models/
│   ├── __init__.py
│   └── mcp_config.py           # Configuration settings model
├── controllers/
│   ├── __init__.py
│   └── mcp_endpoint.py         # HTTP controller for MCP protocol
├── tools/
│   ├── __init__.py
│   ├── terminal.py             # Command execution
│   ├── database.py             # SQL operations via Odoo cursor
│   ├── filesystem.py           # File operations
│   ├── odoo_tools.py           # Odoo shell, modules, config, services
│   └── registry.py             # Tool registry and schemas
├── services/
│   ├── __init__.py
│   ├── mcp_server.py           # MCP JSON-RPC handler
│   └── phone_home.py           # Registration and heartbeat
├── security/
│   ├── __init__.py
│   ├── security.py             # Audit, rate limiting, path validation
│   └── ir.model.access.csv    # Access control
├── data/
│   └── mcp_data.xml            # Default configuration parameters
├── views/
│   └── mcp_config_views.xml    # Configuration UI
└── static/
    └── description/
        └── icon.png            # Module icon
```

### Extending the Module

To add a new tool:

1. Create the tool function in `tools/` (e.g., `tools/my_tool.py`)
2. Add the function to `tools/__init__.py`
3. Register it in `tools/registry.py` in both `get_tool_registry()` and `get_tool_schemas()`
4. Update capabilities in `controllers/mcp_endpoint.py`

## License

LGPL-3 (compatible with Odoo's licensing)

## Support

For issues and questions:
- Check module logs: `/var/log/odoo/odoo.log`
- Check audit logs: `/var/log/odoo/mcp_audit.log`
- Review configuration: Settings > MCP Server
- Open an issue on GitHub

## Changelog

### Version 1.0.0 (2026-02-16)

- Initial release as Odoo V18 module
- 13 tools for Odoo development and administration
- 5 MCP resources
- Phone-home registration on module installation
- Complete audit logging
- HTTP/SSE transport via Odoo controller
- Rate limiting and security controls
- Configuration UI in Odoo Settings
