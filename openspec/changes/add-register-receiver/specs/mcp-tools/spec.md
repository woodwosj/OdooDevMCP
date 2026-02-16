## ADDED Requirements

### Requirement: Register Receiver Tool
The system SHALL provide an MCP tool named `register_receiver` that allows AI agents to dynamically set a callback/receiver URL for phone-home notifications. The tool handler SHALL be implemented in `tools/receiver.py` and registered in `tools/registry.py` in both `get_tool_registry()` and `get_tool_schemas()`.

#### Scenario: Register a receiver URL
- **WHEN** an agent calls the `register_receiver` tool with `receiver_url` set to `https://abc123.ngrok.io`
- **THEN** the system SHALL store `https://abc123.ngrok.io` in the `mcp.phone_home_url` config parameter
- **AND** immediately call `register_server(env)` to POST server registration to `https://abc123.ngrok.io/register`
- **AND** return a success dict containing `server_id`, `url_stored`, and `heartbeat_schedule` fields

#### Scenario: URL normalization strips /register suffix
- **WHEN** an agent calls `register_receiver` with `receiver_url` set to `https://abc123.ngrok.io/register`
- **THEN** the system SHALL strip the `/register` suffix and store `https://abc123.ngrok.io` as the base URL in `mcp.phone_home_url`

#### Scenario: URL normalization strips trailing slash
- **WHEN** an agent calls `register_receiver` with `receiver_url` set to `https://abc123.ngrok.io/`
- **THEN** the system SHALL strip the trailing slash and store `https://abc123.ngrok.io` as the base URL

#### Scenario: Invalid or empty URL rejected
- **WHEN** an agent calls `register_receiver` with an empty string or malformed URL
- **THEN** the system SHALL raise a ValueError with a descriptive error message
- **AND** SHALL NOT modify `mcp.phone_home_url` or call `register_server()`

### Requirement: Register Receiver Rate Limiting
The `register_receiver` tool SHALL be rate limited to a maximum of 5 calls per 60-second sliding window, using the existing `check_rate_limit()` security function with category `'register_receiver'`.

#### Scenario: Rate limit enforced
- **WHEN** an agent calls `register_receiver` more than 5 times within 60 seconds
- **THEN** the system SHALL raise a `RuntimeError` with a rate limit exceeded message
- **AND** the 6th call SHALL NOT modify `mcp.phone_home_url` or trigger registration

### Requirement: Register Receiver Audit Logging
The `register_receiver` tool SHALL log every invocation via the `audit_log()` function with `tool='register_receiver'` and `receiver_url` as a logged field.

#### Scenario: Successful call is audit logged
- **WHEN** an agent calls `register_receiver` with a valid URL
- **THEN** the system SHALL write an audit log entry containing the tool name and the receiver URL

### Requirement: Register Receiver Tool Schema
The `register_receiver` tool SHALL be registered in `get_tool_schemas()` with: description `"Register a receiver URL for phone-home notifications and heartbeats"`, a required `receiver_url` string parameter described as `"Base URL of the receiver server (e.g., https://abc123.ngrok.io)"`.

#### Scenario: Tool appears in MCP tools/list
- **WHEN** an MCP client sends a `tools/list` JSON-RPC request
- **THEN** the response SHALL include `register_receiver` with its description and parameter schema

### Requirement: Register Receiver Handler Signature
The `register_receiver` handler function SHALL follow the project tool pattern: `def register_receiver(env, receiver_url: str) -> dict:` with `env` as the first argument (Odoo environment), returning a dict result.

#### Scenario: Handler follows tool convention
- **WHEN** `call_tool(env, 'register_receiver', {'receiver_url': 'https://example.com'})` is invoked
- **THEN** the registry SHALL dispatch to `receiver.register_receiver(env, receiver_url='https://example.com')`
- **AND** the handler SHALL return a dict (not raise an exception for valid input)
