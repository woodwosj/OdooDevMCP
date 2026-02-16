## 1. Auth and Route Migration

- [x] 1.1 Update controller route `type='json'` to `type='jsonrpc'` on `/mcp/v1`
- [x] 1.2 Update controller `auth='none'` to `auth='bearer'` on `/mcp/v1` and `/mcp/v1/capabilities`
- [x] 1.3 Remove manual `_check_auth()` method from controller (replaced by native bearer auth)

## 2. Deprecated Config Cleanup

- [ ] 2.1 Remove `mcp_api_key` field reference from `views/mcp_config_views.xml`
- [ ] 2.2 Verify `mcp_api_key` field is removed from `models/mcp_config.py` (confirmed removed)
- [ ] 2.3 Remove `mcp.api_key` default value from `data/mcp_data.xml` if present

## 3. Manifest and Dependencies

- [x] 3.1 Update `__manifest__.py` version to `19.0.1.0.0`
- [ ] 3.2 Create `requirements.txt` with Python dependencies (mcp, psycopg2-binary, pyyaml, requests, pydantic)

## 4. Deployment Automation

- [ ] 4.1 Create deployment script (`deploy.sh`) to rsync module to VPS `/opt/odoo/custom-addons/`
- [ ] 4.2 Script should install pip requirements on VPS
- [ ] 4.3 Script should restart Odoo service and trigger module upgrade

## 5. Deployment and Verification

- [ ] 5.1 Deploy module to VPS at 155.138.201.83
- [ ] 5.2 Verify module installs without errors in Odoo log
- [ ] 5.3 Verify `/mcp/v1/health` endpoint responds with healthy status
- [ ] 5.4 Verify `/mcp/v1` endpoint authenticates with Odoo API key (bearer token)
- [ ] 5.5 Verify `/mcp/v1/capabilities` returns tool list with bearer auth
