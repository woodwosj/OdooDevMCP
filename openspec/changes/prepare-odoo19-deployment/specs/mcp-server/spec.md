## MODIFIED Requirements

### Requirement: MCP Endpoint Authentication
The MCP server SHALL authenticate all requests to protected endpoints using Odoo 19's native `auth='bearer'` mechanism. The server SHALL NOT implement custom authentication logic. Authentication is handled automatically by Odoo's API key framework (`res.users.apikeys`). The health check endpoint SHALL remain unauthenticated (`auth='none'`).

#### Scenario: Authenticated request to main endpoint
- **WHEN** a client sends a POST request to `/mcp/v1` with a valid `Authorization: Bearer <api_key>` header
- **THEN** Odoo's native bearer auth validates the API key against `res.users.apikeys`
- **AND** the request is processed by `MCPServerHandler`
- **AND** a JSON-RPC response is returned

#### Scenario: Unauthenticated request to main endpoint
- **WHEN** a client sends a POST request to `/mcp/v1` without a valid bearer token
- **THEN** Odoo's native auth framework rejects the request
- **AND** an HTTP 401 or 403 response is returned (no custom error handling needed)

#### Scenario: Health check remains public
- **WHEN** a client sends a GET request to `/mcp/v1/health`
- **THEN** the server responds with status, version, and Odoo version
- **AND** no authentication is required (`auth='none'`)

#### Scenario: Capabilities endpoint requires authentication
- **WHEN** a client sends a GET request to `/mcp/v1/capabilities` with a valid bearer token
- **THEN** the server returns the list of available tools and resources
- **AND** authentication is enforced via `auth='bearer'`

### Requirement: MCP Route Transport Type
The MCP server's main JSON-RPC endpoint SHALL use `type='jsonrpc'` in its route decorator, conforming to Odoo 18.1+ naming conventions (changelog #183636). The `type='json'` alias is deprecated and SHALL NOT be used.

#### Scenario: Route uses jsonrpc type
- **WHEN** the `/mcp/v1` route is registered with Odoo's HTTP framework
- **THEN** the route decorator specifies `type='jsonrpc'`
- **AND** Odoo handles JSON-RPC request/response serialization natively

### Requirement: Configuration Parameters
The MCP server settings SHALL NOT include a custom `mcp.api_key` configuration parameter. Authentication SHALL be managed exclusively through Odoo's native API key system (`Settings > Users > API Keys`). The Settings UI SHALL NOT display an API key input field.

#### Scenario: API key field removed from settings
- **WHEN** an administrator opens the MCP Server Configuration settings form
- **THEN** no API key input field is displayed
- **AND** authentication is managed through Odoo's standard API Keys interface

#### Scenario: Configuration model has no api_key field
- **WHEN** the `mcp.config.settings` transient model is loaded
- **THEN** it does not define an `mcp_api_key` field
- **AND** no `mcp.api_key` config parameter is written to `ir.config_parameter`

## REMOVED Requirements

### Requirement: Custom API Key Authentication
**Reason**: Replaced by Odoo 19's native `auth='bearer'` mechanism which validates against `res.users.apikeys`. Custom `_check_auth()` logic and the `mcp.api_key` config parameter are no longer needed.
**Migration**: Use Odoo's built-in API key management: Settings > Users > select user > API Keys tab. Generate an API key and use it as the Bearer token in MCP client configuration.
