# Project Context

## Purpose
Odoo Dev MCP Server — an Odoo module that exposes a Model Context Protocol (MCP) server within Odoo's process. It gives AI development agents (Claude Code, IDE integrations) root-level terminal control, direct PostgreSQL database access, filesystem operations, Odoo shell execution, and module/service management — all through a standardized MCP endpoint at `/mcp/v1`.

On module installation/server start, it phones home to a configured API endpoint with hostname, IP addresses, port, Odoo version, database name, and capabilities for fleet discovery.

**Target deployment:** Odoo.sh (custom-addons) and self-hosted Odoo instances.

## Tech Stack
- **Framework:** Odoo 19.0 (Python module)
- **Language:** Python 3.10+
- **Database:** PostgreSQL (accessed via Odoo's `env.cr` cursor)
- **MCP Protocol:** JSON-RPC 2.0 over HTTP (protocol version `2024-11-05`), hand-rolled handler (`MCPServerHandler` class) — does NOT use the `mcp` Python SDK decorator pattern at runtime
- **Transport:** HTTP POST via Odoo HTTP controller at `/mcp/v1`
- **Auth:** Odoo 19 native `auth='bearer'` — authenticates via `Authorization: Bearer <api_key>` header against Odoo API keys; falls back to session auth when header is absent. `save_session=False` by default.
- **Route type:** `type='jsonrpc'` (renamed from `type='json'` in Odoo 18.1; see changelog #183636)
- **Config Storage:** `ir.config_parameter` with Settings UI (`res.config.settings` via `mcp.config.settings` transient model)
- **Dependencies:** `mcp`, `psycopg2`, `pyyaml`, `requests`, `pydantic` (declared in manifest `external_dependencies`)

## Project Conventions

### Code Style
- PEP 8 with Odoo conventions (4-space indent, `_logger` naming)
- `# -*- coding: utf-8 -*-` header on all Python files
- Private methods prefixed with `_` (e.g., `_check_auth`, `_validate_path`)
- Use `_logger = logging.getLogger(__name__)` per module
- Odoo ORM field style: `snake_case` for fields, `PascalCase` for model classes
- Config parameters namespaced as `mcp.*` (e.g., `mcp.api_key`, `mcp.phone_home_url`)
- No type annotations on Odoo model methods (ORM doesn't support them well); use them on service/utility code
- Manifest version: `19.0.1.0.0` (Odoo 19 format: major.minor.patch.build.revision)

### Architecture Patterns
- **Odoo module structure:** `models/`, `controllers/`, `views/`, `data/`, `security/`, plus custom dirs `tools/`, `services/`
- **Tool registry pattern:** `tools/registry.py` maps tool names to handler functions via `get_tool_registry()` dict; `get_tool_schemas()` provides JSON schemas; `call_tool()` dispatches by name
- **MCP server handler:** `services/mcp_server.py` — `MCPServerHandler` class routes JSON-RPC methods (`initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`)
- **Separation of concerns:**
  - `controllers/` — HTTP endpoint only, delegates to `MCPServerHandler` (auth handled by Odoo's `auth='bearer'`)
  - `services/` — MCP protocol handling (`mcp_server.py`), phone-home registration (`phone_home.py`)
  - `tools/` — Individual tool implementations (terminal, database, filesystem, odoo_tools) + registry
  - `security/` — Audit logging, rate limiting, path validation, sensitive config masking
  - `models/` — Odoo ORM configuration only (`mcp.config.settings` transient model)
- **Database access:** Use `request.env.cr` in controller context, never raw `psycopg2` connections
- **Configuration:** All config via `ir.config_parameter`, editable in Settings > MCP Server
- **Phone-home:** Triggered by `post_init_hook` on module install/upgrade; includes retry with exponential backoff

### HTTP Endpoints
| Endpoint | Type | Auth | Method | Purpose |
|----------|------|------|--------|---------|
| `/mcp/v1` | `jsonrpc` | `bearer` | POST | Main MCP JSON-RPC endpoint |
| `/mcp/v1/health` | `http` | `none` | GET | Health check (unauthenticated, returns status/version) |
| `/mcp/v1/capabilities` | `http` | `bearer` | GET | Lists available tools and resources |

### MCP Tools (13 total)
| Tool | Module | Description |
|------|--------|-------------|
| `execute_command` | `terminal.py` | Shell command execution with timeout and env vars |
| `query_database` | `database.py` | Read-only SQL queries with parameterized values |
| `execute_sql` | `database.py` | Write SQL (INSERT, UPDATE, DELETE, DDL) |
| `get_db_schema` | `database.py` | Schema introspection (tables, columns, indexes, constraints) |
| `read_file` | `filesystem.py` | File reading with offset/limit and binary support |
| `write_file` | `filesystem.py` | File writing with append mode and directory creation |
| `odoo_shell` | `odoo_tools.py` | Execute Python code with Odoo ORM `env` access |
| `service_status` | `odoo_tools.py` | Check/manage services (status, start, stop, restart, logs) |
| `read_config` | `odoo_tools.py` | Read Odoo server configuration |
| `list_modules` | `odoo_tools.py` | List modules filtered by state/search |
| `get_module_info` | `odoo_tools.py` | Detailed info about a specific module |
| `install_module` | `odoo_tools.py` | Install a module by technical name |
| `upgrade_module` | `odoo_tools.py` | Upgrade a module by technical name |

### MCP Resources (5 total)
| URI | Description | MIME Type |
|-----|-------------|-----------|
| `odoo://config` | Server configuration (sensitive values masked) | `application/json` |
| `odoo://logs/{service}` | Recent log entries for a service | `text/plain` |
| `odoo://schema/{table}` | Database table schema | `application/json` |
| `odoo://modules` | All installed modules with version info | `application/json` |
| `odoo://system` | System info (hostname, OS, Python version, Odoo version) | `application/json` |

### Configuration Parameters
All stored via `ir.config_parameter`, editable in Settings UI:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mcp.server_host` | `127.0.0.1` | Bind address for MCP HTTP server |
| `mcp.server_port` | `8768` | Port for MCP HTTP server |
| `mcp.log_level` | `info` | Logging verbosity (debug/info/warning/error) |
| `mcp.phone_home_url` | *(empty)* | Fleet registry API URL (empty = disabled) |
| `mcp.heartbeat_interval` | `60` | Heartbeat interval in seconds |
| `mcp.phone_home_retry_count` | `3` | Phone-home retry attempts |
| `mcp.phone_home_timeout` | `5` | Phone-home HTTP timeout in seconds |
| `mcp.command_timeout` | `30` | Default command execution timeout (seconds) |
| `mcp.command_max_timeout` | `600` | Maximum allowed command timeout (seconds) |
| `mcp.max_read_size_mb` | `10` | Max file size for read operations (MB) |
| `mcp.max_write_size_mb` | `50` | Max file size for write operations (MB) |
| `mcp.query_timeout` | `30` | Default SQL query timeout (seconds) |
| `mcp.max_result_rows` | `1000` | Max rows returned by queries |
| `mcp.audit_enabled` | `True` | Enable audit logging |
| `mcp.audit_log_path` | `/var/log/odoo/mcp_audit.log` | Audit log file path |

### Testing Strategy
- `pytest` + `pytest-asyncio` for unit tests
- Mock external dependencies (PostgreSQL, subprocess, HTTP)
- Tests live in `tests/` directory with `test_*.py` naming
- Target 70%+ coverage on security-critical code (path validation, rate limiting, auth)
- Odoo test classes (`TransactionCase`, `HttpCase`) for integration tests
- Run with `pytest --cov=odoo_dev_mcp --cov-fail-under=70`
- Test files: `test_security.py`, `test_database.py`, `test_terminal.py`, `test_filesystem.py`, `test_phone_home.py`, `test_rate_limiter.py`, `test_odoo_shell.py`, `test_config.py`

### Git Workflow
- Feature branches off `main`
- Commit messages: imperative mood, concise (e.g., "Fix symlink path traversal in security.py")
- Review required before merge (use code-reviewer agent)
- No force-push to `main`

## Domain Context
- **MCP (Model Context Protocol):** Anthropic's open protocol for AI agents to interact with tools. Uses JSON-RPC 2.0 over HTTP. Clients send `tools/call` requests, server returns results. Also supports `resources/list` and `resources/read` for static data exposure.
- **Odoo.sh:** Odoo's SaaS hosting platform. Custom modules go in `custom-addons/`. No root/systemd access. Modules run inside Odoo's process. Python deps via `requirements.txt`.
- **Phone-home:** On install, the module POSTs `{server_id, hostname, ip_addresses, port, transport, version, odoo_version, database, capabilities, started_at}` to a fleet registry API so the org knows which servers have the MCP module active. Includes retry with exponential backoff and a separate `/heartbeat` endpoint for ongoing health pings.
- **This is a dev/admin tool, not end-user facing.** It exposes powerful capabilities (shell, SQL, filesystem) to authorized AI agents only.

## Important Constraints
- **Odoo.sh limitations:** No systemd, no root shell, limited subprocess. Module must work within Odoo's process.
- **Security:** All operations audit-logged to file. In-memory sliding-window rate limiting enforced per-database. Path traversal prevention with symlink resolution required. Bearer token auth via Odoo 19's native `auth='bearer'` on all endpoints except health check.
- **Auth:** Uses Odoo's API key system (`res.users.apikeys`). Create API keys in Settings > Users > API Keys. The `auth='bearer'` decorator handles validation automatically — no custom auth code needed.
- **No stdio transport:** Odoo.sh doesn't support stdin/stdout-based MCP. HTTP only.
- **Odoo 19 compatibility:** Must use `auth='bearer'` and `type='jsonrpc'` (not the deprecated `type='json'`). Auth handled natively by Odoo's API key framework.
- **Single-database:** Each Odoo instance serves one database. MCP tools operate on that database.

## External Dependencies
- **Fleet Registry API** — Configurable URL that receives phone-home POST on module install. Endpoint configured via `mcp.phone_home_url`. No auth token for phone-home requests (not yet implemented).
- **MCP Clients** — Claude Code, Claude Desktop, VS Code extensions, or any MCP-compatible client connecting over HTTP to `/mcp/v1`.
- **Odoo ORM** — All database operations go through Odoo's cursor (`env.cr`) and registry.
- **PostgreSQL** — Underlying database, accessed indirectly via Odoo's connection pool.

## File Map
```
odoo_dev_mcp/
├── __manifest__.py           # Module manifest (v19.0.1.0.0, depends: base, web)
├── __init__.py               # Module init + post_init_hook
├── requirements.txt          # Python dependencies (mcp, pyyaml, pydantic, requests, psycopg2)
├── models/
│   ├── __init__.py
│   └── mcp_config.py         # mcp.config.settings transient model (16 config params)
├── controllers/
│   ├── __init__.py
│   └── mcp_endpoint.py       # HTTP routes: /mcp/v1, /mcp/v1/health, /mcp/v1/capabilities
├── services/
│   ├── __init__.py
│   ├── mcp_server.py         # MCPServerHandler: JSON-RPC dispatch for MCP protocol
│   └── phone_home.py         # register_server(), send_heartbeat(), get_network_info()
├── tools/
│   ├── __init__.py
│   ├── registry.py           # Tool registry: name→handler mapping + JSON schemas
│   ├── terminal.py           # execute_command
│   ├── database.py           # query_database, execute_sql, get_db_schema
│   ├── filesystem.py         # read_file, write_file
│   └── odoo_tools.py         # odoo_shell, service_status, read_config, list/get/install/upgrade modules
├── security/
│   ├── __init__.py
│   ├── security.py           # audit_log(), validate_path(), mask_sensitive_config(), check_rate_limit()
│   └── ir.model.access.csv   # ORM access rules
├── views/
│   └── mcp_config_views.xml  # Settings UI
├── data/
│   └── mcp_data.xml          # Default data records
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures
│   ├── test_security.py
│   ├── test_database.py
│   ├── test_terminal.py
│   ├── test_filesystem.py
│   ├── test_phone_home.py
│   ├── test_rate_limiter.py
│   ├── test_odoo_shell.py
│   └── test_config.py
└── openspec/                 # Spec-driven development
    ├── project.md            # This file
    ├── AGENTS.md             # OpenSpec instructions
    ├── specs/                # Current truth
    └── changes/              # Active proposals
```
