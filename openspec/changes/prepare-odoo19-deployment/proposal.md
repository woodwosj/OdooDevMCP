# Change: Prepare Odoo 19 VPS Deployment

## Why
The OdooDevMCP module needs to be deployed to a production Odoo 19 VPS (155.138.201.83) at `/opt/odoo/custom-addons/`. The module's authentication and route configuration must align with Odoo 19's native patterns, deprecated custom auth must be cleaned up, and deployment automation is needed to reliably push and install the module on the target server.

## What Changes
- **BREAKING**: Migrate `auth='none'` + manual `_check_auth()` to Odoo 19 native `auth='bearer'` on all authenticated endpoints (already done in controller code)
- **BREAKING**: Migrate `type='json'` to `type='jsonrpc'` per Odoo 18.1+ changelog #183636 (already done in controller code)
- Remove deprecated `mcp.api_key` config parameter field from Settings UI (view still references it; model already cleaned up)
- Update manifest version to `19.0.1.0.0` (already done)
- Create `requirements.txt` for Python dependencies on VPS
- Create deployment script to push module to VPS and trigger install/upgrade

## Impact
- Affected specs: `mcp-server` (auth and route type changes)
- Affected code:
  - `controllers/mcp_endpoint.py` — route decorators (already updated)
  - `models/mcp_config.py` — `mcp_api_key` field (already removed from model)
  - `views/mcp_config_views.xml` — API key field still present in UI, must be removed
  - `__manifest__.py` — version (already updated to `19.0.1.0.0`)
  - New files: `requirements.txt`, deployment script
- Affected infrastructure: VPS at 155.138.201.83, `/opt/odoo/custom-addons/`
- No data migration needed: `mcp.api_key` was an `ir.config_parameter` with no ORM storage implications
