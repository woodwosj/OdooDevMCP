## ADDED Requirements

### Requirement: Phone-Home Base URL Convention
The system SHALL store a base URL (without path) in the `mcp.phone_home_url` configuration parameter. The `register_server()` function SHALL append `/register` to this base URL when POSTing server registration data. The `send_heartbeat()` function SHALL append `/heartbeat` to this base URL when POSTing heartbeat pings.

#### Scenario: Registration uses /register path
- **WHEN** `mcp.phone_home_url` is set to `https://example.com`
- **AND** `register_server(env)` is called
- **THEN** the registration payload SHALL be POSTed to `https://example.com/register`

#### Scenario: Heartbeat uses /heartbeat path
- **WHEN** `mcp.phone_home_url` is set to `https://example.com`
- **AND** `send_heartbeat(env)` is called
- **THEN** the heartbeat payload SHALL be POSTed to `https://example.com/heartbeat`

#### Scenario: Trailing slash in base URL is handled
- **WHEN** `mcp.phone_home_url` is set to `https://example.com/`
- **AND** `register_server(env)` is called
- **THEN** the trailing slash SHALL be stripped before appending `/register`, resulting in a POST to `https://example.com/register`

#### Scenario: Phone-home disabled when URL is empty
- **WHEN** `mcp.phone_home_url` is empty or not set
- **AND** `register_server(env)` or `send_heartbeat(env)` is called
- **THEN** the function SHALL return `False` without making any HTTP request

### Requirement: Dynamic Capabilities List in Registration
The `register_server()` function SHALL build the `capabilities` list dynamically by reading tool names from `get_tool_registry().keys()` instead of using a hardcoded list. The import of `get_tool_registry` SHALL occur inside the function body to avoid circular imports.

#### Scenario: New tools are automatically included in registration
- **WHEN** a new tool is added to `get_tool_registry()` in `tools/registry.py`
- **AND** `register_server(env)` is called
- **THEN** the registration payload `capabilities` field SHALL include the new tool name without any code changes to `phone_home.py`

#### Scenario: Registration payload contains all registered tools
- **WHEN** `register_server(env)` is called
- **THEN** the `capabilities` list in the payload SHALL contain exactly the keys returned by `get_tool_registry().keys()`, converted to a sorted list

### Requirement: Phone-Home Registration Payload
The `register_server()` function SHALL POST a JSON payload containing: `server_id` (string, `{dbname}_{hostname}`), `hostname` (string), `ip_addresses` (object with `primary` and `all` keys), `port` (integer from `mcp.server_port`), `transport` (string, `"http/sse"`), `version` (string, `"1.0.0"`), `odoo_version` (string from `odoo.release`), `database` (string, database name), `capabilities` (list of tool names), and `started_at` (ISO 8601 UTC timestamp).

#### Scenario: Successful registration
- **WHEN** `mcp.phone_home_url` is configured
- **AND** `register_server(env)` is called
- **AND** the remote endpoint responds with HTTP 200 or 201
- **THEN** the function SHALL return `True` and log a success message

#### Scenario: Registration with retry and backoff
- **WHEN** the remote endpoint is unreachable or returns an error
- **THEN** the function SHALL retry up to `mcp.phone_home_retry_count` times (default 3) with exponential backoff (2^attempt seconds)
- **AND** if all retries fail, the function SHALL return `False` and log an error

### Requirement: Heartbeat Payload
The `send_heartbeat()` function SHALL POST a JSON payload containing: `server_id` (string, `{dbname}_{hostname}`), `status` (string, `"healthy"`), and `timestamp` (ISO 8601 UTC timestamp).

#### Scenario: Successful heartbeat
- **WHEN** `mcp.phone_home_url` is configured
- **AND** `send_heartbeat(env)` is called
- **AND** the remote endpoint responds with HTTP 200 or 201
- **THEN** the function SHALL return `True`

#### Scenario: Failed heartbeat
- **WHEN** the remote endpoint is unreachable or returns an error
- **THEN** the function SHALL return `False` and log a warning (no retry for heartbeats)

### Requirement: Heartbeat Cron Job
The system SHALL provide an `AbstractModel` with `_name = 'mcp.heartbeat'` that implements a `_cron_send_heartbeat()` method. A corresponding `ir.cron` record SHALL trigger this method every 1 minute. The cron record SHALL use `noupdate="0"` so it updates on module upgrade. The cron SHALL use Odoo 18+ format: `state="code"` with `code` field set to `model._cron_send_heartbeat()`, without `numbercall` or `doall` fields.

#### Scenario: Cron triggers heartbeat
- **WHEN** the heartbeat cron fires
- **AND** `mcp.phone_home_url` is configured
- **THEN** `send_heartbeat(env)` SHALL be called and a heartbeat POST SHALL be sent to `{base_url}/heartbeat`

#### Scenario: Cron is safe when phone-home is disabled
- **WHEN** the heartbeat cron fires
- **AND** `mcp.phone_home_url` is empty
- **THEN** `send_heartbeat(env)` SHALL return `False` without making any HTTP request and without raising an exception

### Requirement: Dynamic Capabilities Endpoint
The `/mcp/v1/capabilities` HTTP endpoint SHALL return the tool list dynamically by reading from `get_tool_registry().keys()` instead of a hardcoded list. The resource list MAY remain hardcoded.

#### Scenario: Capabilities endpoint reflects registered tools
- **WHEN** a GET request is made to `/mcp/v1/capabilities` with valid bearer authentication
- **THEN** the response JSON `tools` array SHALL contain exactly the tool names from `get_tool_registry().keys()`

#### Scenario: New tool appears in capabilities without code change
- **WHEN** a new tool `register_receiver` is added to `get_tool_registry()`
- **AND** a GET request is made to `/mcp/v1/capabilities`
- **THEN** the response `tools` array SHALL include `"register_receiver"`
