---
name: "odoo-dev"
description: "Triggered when users ask about Odoo development, debugging, deploying, or managing Odoo modules and instances. Handles tasks like writing Odoo models, views, controllers, security rules, ORM code, module installation, database inspection, server management, and troubleshooting Odoo errors. Use this skill for any work involving an Odoo instance connected via the odoo-dev-mcp server."
version: "1.1.0"
---

# Odoo Development with MCP Server

You are an expert Odoo developer with access to a live Odoo instance through the `odoo-dev-mcp` MCP server. This server exposes 14 tools over HTTP JSON-RPC at `/mcp/v1` with Bearer token authentication.

## Before You Begin: Look Up Odoo Documentation

Before writing or modifying any Odoo code, ALWAYS consult the official Odoo documentation via Context7 to ensure you are using current APIs and patterns.

**Step 1**: Resolve the library ID for Odoo:
```
mcp__context7__resolve-library-id(libraryName="odoo", query="<your specific question>")
```

**Step 2**: Query the docs with your specific question:
```
mcp__context7__query-docs(libraryId="<resolved-id>", query="<your specific question>")
```

Do this for any of the following before writing code:
- ORM API usage (fields, methods, decorators)
- View definitions (form, list, kanban, search)
- Security model (ir.model.access.csv, ir.rule)
- Controller patterns (http.route, auth types)
- Report/QWeb templates
- Cron job definitions
- Mixin classes and inheritance patterns
- Widget types and client-side JS

## Connection Workflow

Always verify connectivity before starting work.

**1. Health check** (unauthenticated):
The MCP server exposes a health endpoint. If your MCP connection is working, the tools are available. If you suspect connectivity issues, use `execute_command` to curl the health endpoint:
```
execute_command(command="curl -s http://localhost:8069/mcp/v1/health")
```

**2. Verify tool access**:
Call `list_modules` or `read_config` as a quick smoke test that authenticated tools are functioning.

**3. Register receiver** (optional, for phone-home during development):
```
register_receiver(receiver_url="https://your-receiver.ngrok.io")
```

## Deploying to a New Odoo.sh Environment

When deploying the MCP module to a new Odoo.sh instance (or any remote Odoo), follow this process to ensure heartbeats reach your local development machine automatically.

### Step 1: Start the Local Receiver

The receiver is a lightweight Flask server that catches registration and heartbeat POSTs from remote Odoo instances.

```bash
cd receiver/
pip install -r requirements.txt
python server.py --ngrok --port 5000
```

This starts:
- Flask receiver on `http://127.0.0.1:5000`
- ngrok tunnel providing a public HTTPS URL (printed to console)

Note the ngrok URL (e.g., `https://abc123.ngrok-free.app`).

### Step 2: Set the Receiver URL in Module Data

Before pushing the module to the target repo, set `mcp.phone_home_url` in `data/mcp_data.xml`:

```xml
<record id="mcp_config_phone_home_url" model="ir.config_parameter">
    <field name="key">mcp.phone_home_url</field>
    <field name="value">https://abc123.ngrok-free.app</field>
</record>
```

This goes inside the `<data noupdate="1">` block. On module install, Odoo writes this ICP value, and the `post_init_hook` immediately sends a registration POST to your receiver.

### Step 3: Push Only Module Files

When adding the module to a client repo (e.g., an Odoo.sh project), include ONLY the Odoo module files:

```
odoo_dev_mcp/
  __init__.py
  __manifest__.py
  controllers/
  data/
  models/
  security/
  services/
  static/description/icon.png
  tools/
  views/
```

**Exclude**: `receiver/`, `tests/`, `skills/`, `openspec/`, `deploy.sh`, all root-level `.md` files, `__pycache__/`, `.git/`

### Step 4: Clean External Dependencies

The manifest's `external_dependencies` must only list packages available on Odoo.sh. Remove any that aren't actually imported:

```python
'external_dependencies': {
    'python': [
        'psycopg2',
        'requests',
    ],
},
```

Do NOT include `mcp`, `pydantic`, or `pyyaml` — they are not used by the module runtime and will cause Odoo.sh builds to fail.

### Step 5: Adjust Paths for Odoo.sh

Odoo.sh uses different filesystem paths than a VPS:
- Audit log path: `/home/odoo/logs/mcp_audit.log` (not `/var/log/odoo/`)
- Module path: managed by Odoo.sh (no `/opt/odoo/custom-addons/`)
- No systemd — `service_status` log fallback reads files directly

### Step 6: Install and Verify

After Odoo.sh rebuilds from your push:
1. Go to **Apps > Update Apps List**
2. Search for **Odoo Dev MCP Server** and install
3. The `post_init_hook` fires → sends registration to your local receiver
4. Cron fires every minute → sends enriched heartbeats

Monitor locally:
```bash
curl http://127.0.0.1:5000/servers
```

### What Happens Automatically

Once installed with a receiver URL configured:
- **On install**: `post_init_hook` sends full server registration (hostname, IPs, capabilities, Odoo version, database name)
- **Every minute**: Cron sends enriched heartbeat (all server info + status + uptime)
- **On Odoo.sh rebuild**: Health endpoint detects hostname change → triggers re-registration → cron sends updated heartbeat within 1 minute
- **No API key needed** for heartbeats — they use the server's own ORM environment

### ngrok URL Expiry

Free ngrok URLs change on restart. When your tunnel restarts:
- Either update `mcp.phone_home_url` via Settings > Technical > System Parameters on the Odoo instance
- Or push a new commit with the updated URL in `mcp_data.xml` (requires module upgrade since `noupdate="1"`)
- Or use `register_receiver` tool if you have an API key configured

## Available MCP Tools Reference

### Exploration Tools

**get_db_schema** - Retrieve database schema information
```
Parameters:
  action: string (required) - "list_tables" | "describe_table" | "list_indexes" | "list_constraints"
  table_name: string - Required for describe_table, list_indexes, list_constraints
  schema_name: string - PostgreSQL schema (default: "public")

Returns: tables/columns/indexes/constraints depending on action
```

**list_modules** - List Odoo modules with installation status
```
Parameters:
  state: string - "installed" | "uninstalled" | "to_upgrade" | "to_install" | "to_remove" | "all" (default: "all")
  search: string - Search term to filter by name or description
  limit: integer - Max modules to return (default: 100)

Returns: { modules: [...], total_count, returned_count, filter_applied }
```

**get_module_info** - Get detailed information about a specific module
```
Parameters:
  module_name: string (required) - Technical name of the module

Returns: { name, display_name, version, state, author, summary, description, category, website, dependencies, installed_version }
```

**read_file** - Read file contents from the Odoo server filesystem
```
Parameters:
  path: string (required) - Absolute path to the file
  encoding: string - "utf-8" (default) or "binary" (base64 output)
  offset: integer - Line number to start from (1-based, 0 = start)
  limit: integer - Max lines to return (0 = entire file)

Returns: { path, content, size_bytes, lines_returned, total_lines, truncated, encoding }
```

**read_config** - Read the Odoo server configuration
```
Parameters:
  key: string - Specific config key (null = return all, sensitive values masked)

Returns: { config_path, values } or { config_path, key, value }
```

**query_database** - Execute read-only SQL against PostgreSQL
```
Parameters:
  query: string (required) - SELECT or read-only SQL
  params: array - Parameterized query values
  limit: integer - Max rows to return (default: 1000)

Returns: { columns, rows, row_count, truncated, duration_ms }
```

### Development Tools

**odoo_shell** - Execute Python/ORM code in the Odoo environment
```
Parameters:
  code: string (required) - Python code to execute (env, cr, uid, context are available)
  timeout: integer - Max execution time in seconds (default: 30, max: 300)

Returns: { output, return_value, error, duration_ms }

The execution context provides:
  env   - Odoo Environment (same as self.env in a model method)
  cr    - Database cursor
  uid   - Current user ID
  context - Odoo context dict
```

**write_file** - Write content to a file on the Odoo server
```
Parameters:
  path: string (required) - Absolute path to the file
  content: string (required) - Content to write
  encoding: string - "utf-8" (default) or "binary" (base64 input)
  mode: string - "overwrite" (default) or "append"
  create_directories: boolean - Create parent dirs if missing (default: true)

Returns: { path, bytes_written, created }
```

**execute_command** - Execute a shell command on the Odoo server
```
Parameters:
  command: string (required) - Shell command to execute
  working_directory: string - Working directory (default: /opt/odoo)
  timeout: integer - Max seconds (default: 30, max from config)
  env_vars: object - Additional environment variables

Returns: { stdout, stderr, exit_code, timed_out, duration_ms }
```

**execute_sql** - Execute write SQL (INSERT, UPDATE, DELETE, DDL)
```
Parameters:
  statement: string (required) - SQL statement
  params: array - Parameterized values

Returns: { affected_rows, status_message, duration_ms }
```

### Deployment Tools

**install_module** - Install an Odoo module
```
Parameters:
  module_name: string (required) - Technical name of the module

Returns: { success, message, state }
```

**upgrade_module** - Upgrade an installed Odoo module
```
Parameters:
  module_name: string (required) - Technical name of the module

Returns: { success, message, state }
```

**service_status** - Check and manage services (odoo, postgresql, nginx)
```
Parameters:
  service: string - Service name (default: "odoo"). Allowed: odoo, postgresql, nginx
  action: string - "status" | "start" | "stop" | "restart" | "logs" (default: "status")
  log_lines: integer - Lines to return for logs action (default: 50, max: 1000)

Returns: { service, active, status, pid, memory_mb, uptime, description } or log data

Note: On Odoo.sh, systemctl is unavailable. The logs action falls back to reading
log files directly from /home/odoo/logs/ or /var/log/odoo/.
```

### Utility Tools

**register_receiver** - Register a phone-home receiver URL
```
Parameters:
  receiver_url: string (required) - Base URL (e.g., https://abc123.ngrok.io)

Returns: { success, server_id, url_stored, registration_sent, heartbeat_schedule }
```

## Development Workflows

### Exploring an Unfamiliar Instance

Follow this sequence to understand what you are working with:

1. Read the server configuration to understand paths and database setup:
   ```
   read_config()
   ```

2. List installed modules to understand what is deployed:
   ```
   list_modules(state="installed")
   ```

3. If investigating a specific module, get its details and dependencies:
   ```
   get_module_info(module_name="sale")
   ```

4. Inspect database tables relevant to your task:
   ```
   get_db_schema(action="list_tables")
   get_db_schema(action="describe_table", table_name="sale_order")
   ```

5. Read module source files on the server:
   ```
   read_file(path="/opt/odoo/odoo/addons/sale/models/sale_order.py")
   ```

### Creating a New Module

Before creating any module, look up the current Odoo module structure via Context7.

A minimal Odoo module requires these files:

```
my_module/
  __init__.py
  __manifest__.py
  models/
    __init__.py
    my_model.py
  security/
    ir.model.access.csv
  views/
    my_model_views.xml
```

Step-by-step:

1. **Look up current patterns** via Context7 for manifest format, model definitions, and view syntax.

2. **Create the directory structure** using write_file with create_directories=true:
   ```
   write_file(path="/opt/odoo/custom-addons/my_module/__manifest__.py", content="...")
   write_file(path="/opt/odoo/custom-addons/my_module/__init__.py", content="from . import models")
   write_file(path="/opt/odoo/custom-addons/my_module/models/__init__.py", content="from . import my_model")
   write_file(path="/opt/odoo/custom-addons/my_module/models/my_model.py", content="...")
   ```

3. **Always create security rules**:
   ```
   write_file(path="/opt/odoo/custom-addons/my_module/security/ir.model.access.csv", content="id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink\naccess_my_model,my.model,model_my_model,base.group_user,1,1,1,0")
   ```

4. **Update the module list** and install:
   ```
   execute_command(command="/opt/odoo/odoo-venv/bin/python /opt/odoo/odoo-bin -c /etc/odoo.conf -d <database> --update=base --stop-after-init")
   install_module(module_name="my_module")
   ```

### Modifying an Existing Module

1. **Read the current source** to understand what exists:
   ```
   read_file(path="/opt/odoo/custom-addons/module_name/models/model.py")
   ```

2. **Test your changes** in the shell before writing them:
   ```
   odoo_shell(code="records = env['model.name'].search([], limit=5)\nfor r in records:\n    print(r.name, r.state)")
   ```

3. **Write the modified file**:
   ```
   write_file(path="/opt/odoo/custom-addons/module_name/models/model.py", content="<full file content>")
   ```

4. **Upgrade the module** to apply changes:
   ```
   upgrade_module(module_name="module_name")
   ```

5. **Verify** by testing with odoo_shell or querying the database.

### Debugging Issues

**Check Odoo logs for errors**:
```
service_status(service="odoo", action="logs", log_lines=200)
```

**Inspect data directly via SQL** (faster for large datasets):
```
query_database(query="SELECT id, name, state, create_date FROM sale_order WHERE state = 'draft' ORDER BY create_date DESC", limit=20)
```

**Test ORM operations interactively**:
```
odoo_shell(code="""
order = env['sale.order'].browse(42)
print(f"Order: {order.name}")
print(f"State: {order.state}")
print(f"Lines: {len(order.order_line)}")
for line in order.order_line:
    print(f"  - {line.product_id.name}: {line.product_uom_qty} x {line.price_unit}")
""")
```

**Check access rules**:
```
query_database(query="SELECT model_id, group_id, perm_read, perm_write, perm_create, perm_unlink FROM ir_model_access WHERE model_id IN (SELECT id FROM ir_model WHERE model = %s)", params=["sale.order"])
```

**Check record rules**:
```
query_database(query="SELECT name, model_id, domain_force, groups FROM ir_rule WHERE model_id IN (SELECT id FROM ir_model WHERE model = %s)", params=["sale.order"])
```

### Deploying Changes

1. **Check current service status**:
   ```
   service_status(service="odoo", action="status")
   ```

2. **Upgrade the module** (applies Python, XML, and data changes):
   ```
   upgrade_module(module_name="my_module")
   ```
   Note: This calls `button_immediate_upgrade()` which triggers a full module upgrade cycle including view updates, data file reloads, and model schema changes.

3. **If the upgrade fails**, check logs:
   ```
   service_status(service="odoo", action="logs", log_lines=100)
   ```

4. **For changes that require a full restart** (rare, usually only for controller route changes or deep framework modifications):
   ```
   service_status(service="odoo", action="restart")
   ```

5. **Verify after deployment**:
   ```
   service_status(service="odoo", action="status")
   odoo_shell(code="mod = env['ir.module.module'].search([('name','=','my_module')])\nprint(mod.installed_version, mod.state)")
   ```

## Odoo Development Checklist

When creating or modifying Odoo modules, verify each of these:

### Security (CRITICAL)
- [ ] Every new model has an entry in `security/ir.model.access.csv`
- [ ] Access rights use appropriate groups (base.group_user, base.group_system, etc.)
- [ ] Multi-company record rules exist if the model has a `company_id` field
- [ ] Sensitive operations use `sudo()` only when necessary, and the reason is documented
- [ ] SQL queries use parameterized values (never string formatting with user input)

### Models
- [ ] Model name follows Odoo convention: `module_name.model_name` with dots
- [ ] `_description` is set on every model
- [ ] Computed fields specify `compute`, `store`, and `depends` correctly
- [ ] `onchange` methods are used for UX hints, not business logic
- [ ] Constraints use `@api.constrains` with proper error messages
- [ ] SQL constraints are defined in `_sql_constraints` where appropriate
- [ ] Required fields have sensible defaults where possible
- [ ] Many2one fields specify `ondelete` policy

### Views
- [ ] Form views include `<sheet>` wrapper and `<group>` organization
- [ ] List views show the most important columns
- [ ] Search views define commonly used filters and group-by options
- [ ] Menu items and actions are defined to access the views
- [ ] View inheritance uses correct `inherit_id` and xpath expressions

### Data and Migration
- [ ] Demo data is in `demo/` directory and flagged in manifest
- [ ] Default data is in `data/` directory
- [ ] Version bumps in `__manifest__.py` when schema changes
- [ ] Pre/post migration scripts for breaking changes

### Manifest
- [ ] `name`, `version`, `summary`, `description`, `author`, `category` are set
- [ ] `depends` lists all required modules (direct dependencies only)
- [ ] `data` lists all XML/CSV files in load order (security first, then views, then data)
- [ ] `license` is specified (commonly "LGPL-3")
- [ ] `application` is True only for top-level apps, not libraries
- [ ] `external_dependencies` only lists packages actually imported AND available on the target platform

## Odoo 19 Specific Notes

This server runs Odoo 19. Key differences from older versions:

- Use `auth='bearer'` for API authentication (not custom token schemes)
- Controller `type='jsonrpc'` replaces deprecated `type='json'`
- Use `type='http'` when you need full control of the JSON response (avoids double-wrapping)
- Cron XML records do not support `numbercall` or `doall` fields (removed in Odoo 18+)
- `odoo.tools.config` IS the configmanager instance directly — access `.rcfile`, `.get('db_name')` etc. on it (NOT `odoo.tools.config.configmanager`)
- For `auth='none'` endpoints needing ORM access, use `from odoo.modules.registry import Registry` and build an env manually — `request.env.sudo()` does NOT work without auth
- `odoo.registry()` does NOT exist in Odoo 19 — use `Registry(db_name)` instead
- The `web` module is always installed; assets bundle patterns may differ from Odoo 16/17
- Check Context7 docs for any API changes before assuming Odoo 16/17 patterns still apply

## Common Patterns

### Reading Data Efficiently
For simple lookups, prefer `odoo_shell` with ORM:
```python
odoo_shell(code="recs = env['res.partner'].search([('is_company','=',True)], limit=10)\nfor r in recs:\n    print(r.id, r.name)")
```

For complex joins or aggregations, prefer `query_database` with raw SQL:
```sql
query_database(query="SELECT rp.name, COUNT(so.id) as order_count, SUM(so.amount_total) as total FROM res_partner rp JOIN sale_order so ON so.partner_id = rp.id GROUP BY rp.name ORDER BY total DESC LIMIT 10")
```

### Writing Data Safely
Always test in shell first, then write the actual code:
```python
odoo_shell(code="""
partner = env['res.partner'].create({
    'name': 'Test Partner',
    'email': 'test@example.com',
    'is_company': True,
})
print(f"Created partner {partner.id}: {partner.name}")
""")
```

### Checking Module Dependencies Before Changes
```python
odoo_shell(code="""
mod = env['ir.module.module'].search([('name','=','sale')])
print("Depends on:")
for dep in mod.dependencies_id:
    print(f"  {dep.name} ({dep.state})")
# Also check what depends on this module
rdeps = env['ir.module.module.dependency'].search([('name','=','sale')])
print("Depended on by:")
for rd in rdeps:
    print(f"  {rd.module_id.name} ({rd.module_id.state})")
""")
```

## Rate Limits

The MCP server enforces per-tool rate limits (sliding window per database):
- `execute_command`: 10 calls / 60 seconds
- `query_database`: 100 calls / 60 seconds
- `execute_sql`: 50 calls / 60 seconds
- `read_file`: 50 calls / 60 seconds
- `write_file`: 30 calls / 60 seconds
- `odoo_shell`: 5 calls / 60 seconds
- `register_receiver`: 5 calls / 60 seconds

Plan your operations accordingly. Batch reads where possible. The `odoo_shell` limit is the most restrictive -- combine multiple operations into a single code block rather than making many small calls.

## Error Handling

When a tool call fails:
1. Check the error message in the response
2. For `odoo_shell` errors, the `error` field contains the Python traceback
3. For database errors, check if the table/column exists using `get_db_schema`
4. For file errors, verify the path exists using `execute_command(command="ls -la /path/to/check")`
5. For service errors, check logs: `service_status(service="odoo", action="logs")`
6. If rate-limited, wait and retry after the window resets (60 seconds)

## Known Platform Differences

| Aspect | VPS / Self-hosted | Odoo.sh |
|--------|-------------------|---------|
| Audit log path | `/opt/odoo/logs/mcp_audit.log` | `/home/odoo/logs/mcp_audit.log` |
| Service management | systemctl available | No systemd — logs via file fallback |
| `ODOO_STAGE` env var | Not set (empty string) | `dev`, `staging`, or `production` |
| Hostname stability | Stable | Changes on every rebuild |
| Module path | `/opt/odoo/custom-addons/` | Managed by Odoo.sh git deploy |
| journalctl | May need `systemd-journal` group | Not available |
