"""Shared pytest fixtures for Odoo Dev MCP tests.

Mocks the 'odoo' package in sys.modules so that the OdooDevMCP package
can be imported without an actual Odoo installation. Provides a mock_env
fixture that simulates the Odoo environment with cursor, ICP, uid, etc.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# 1) Mock the entire 'odoo' package tree BEFORE any OdooDevMCP imports.
#    This must happen at module scope so conftest loading does the work
#    before any test module imports from the package.
# ---------------------------------------------------------------------------

# Create real base classes that Odoo models inherit from.
# Using MagicMock as the base would break class creation (metaclass issues).


class _OdooModelBase:
    """Minimal stand-in for odoo.models.Model / TransientModel / AbstractModel."""
    _name = None
    _inherit = None
    _description = None


class _OdooController:
    """Minimal stand-in for odoo.http.Controller."""
    pass


def _route_decorator(*args, **kwargs):
    """Passthrough decorator mimicking odoo.http.route."""
    def wrapper(func):
        return func
    if args and callable(args[0]):
        return args[0]
    return wrapper


def _noop_decorator(*args, **kwargs):
    """Passthrough decorator mimicking odoo.api.model / depends / etc."""
    def wrapper(func):
        return func
    if args and callable(args[0]):
        return args[0]
    return wrapper


# Build the fake odoo module tree
_odoo = types.ModuleType("odoo")
_odoo_models = types.ModuleType("odoo.models")
_odoo_fields = MagicMock()
_odoo_api = MagicMock()
_odoo_http = types.ModuleType("odoo.http")
_odoo_release = types.ModuleType("odoo.release")
_odoo_tools = types.ModuleType("odoo.tools")
_odoo_tools_config = MagicMock()
_odoo_exceptions = types.ModuleType("odoo.exceptions")

# Wire up odoo.models with real classes
_odoo_models.Model = _OdooModelBase
_odoo_models.TransientModel = _OdooModelBase
_odoo_models.AbstractModel = _OdooModelBase

# Wire up odoo.http
_odoo_http.Controller = _OdooController
_odoo_http.route = _route_decorator
_odoo_http.request = MagicMock()
_odoo_http.Response = MagicMock()

# Wire up odoo.api (decorators)
_odoo_api.model = _noop_decorator
_odoo_api.depends = _noop_decorator
_odoo_api.onchange = _noop_decorator
_odoo_api.constrains = _noop_decorator

# Wire up odoo.release
_odoo_release.version = "19.0"

# Wire up odoo.tools.config
_odoo_tools_config.configmanager = MagicMock()
_odoo_tools_config.configmanager.rcfile = "/etc/odoo/odoo.conf"

# Wire up odoo-level attributes used by controllers with auth='none'
_odoo.SUPERUSER_ID = 1

# Mock odoo.modules.registry.Registry for health endpoint hostname detection
_odoo_modules = types.ModuleType("odoo.modules")
_odoo_modules_registry = types.ModuleType("odoo.modules.registry")
_odoo_modules_registry.Registry = MagicMock()
_odoo_modules.registry = _odoo_modules_registry

# Also mock odoo.orm.registry (where it actually lives in Odoo 19)
_odoo_orm = types.ModuleType("odoo.orm")
_odoo_orm_registry = types.ModuleType("odoo.orm.registry")
_odoo_orm_registry.Registry = _odoo_modules_registry.Registry
_odoo_orm.registry = _odoo_orm_registry

# Attach sub-modules to odoo
_odoo.models = _odoo_models
_odoo.modules = _odoo_modules
_odoo.orm = _odoo_orm
_odoo.fields = _odoo_fields
_odoo.api = _odoo_api
_odoo.http = _odoo_http
_odoo.release = _odoo_release
_odoo.tools = _odoo_tools
_odoo.tools.config = _odoo_tools_config
_odoo.exceptions = _odoo_exceptions

# Mock werkzeug (imported by controllers/mcp_endpoint.py)
_werkzeug = types.ModuleType("werkzeug")
_werkzeug_exceptions = types.ModuleType("werkzeug.exceptions")
_werkzeug_exceptions.BadRequest = type("BadRequest", (Exception,), {})
_werkzeug.exceptions = _werkzeug_exceptions

# Inject into sys.modules
sys.modules.setdefault("odoo", _odoo)
sys.modules.setdefault("odoo.models", _odoo_models)
sys.modules.setdefault("odoo.fields", _odoo_fields)
sys.modules.setdefault("odoo.api", _odoo_api)
sys.modules.setdefault("odoo.http", _odoo_http)
sys.modules.setdefault("odoo.release", _odoo_release)
sys.modules.setdefault("odoo.tools", _odoo_tools)
sys.modules.setdefault("odoo.tools.config", _odoo_tools_config)
sys.modules.setdefault("odoo.exceptions", _odoo_exceptions)
sys.modules.setdefault("odoo.modules", _odoo_modules)
sys.modules.setdefault("odoo.modules.registry", _odoo_modules_registry)
sys.modules.setdefault("odoo.orm", _odoo_orm)
sys.modules.setdefault("odoo.orm.registry", _odoo_orm_registry)
sys.modules.setdefault("werkzeug", _werkzeug)
sys.modules.setdefault("werkzeug.exceptions", _werkzeug_exceptions)

# ---------------------------------------------------------------------------
# 2) Add parent directory to sys.path so 'OdooDevMCP' is importable.
# ---------------------------------------------------------------------------
_parent_dir = str(Path(__file__).resolve().parent.parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


# ---------------------------------------------------------------------------
# 3) Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Clear the in-memory rate-limit state between every test."""
    from OdooDevMCP.security.security import _rate_limit_state
    _rate_limit_state.clear()
    yield
    _rate_limit_state.clear()


@pytest.fixture
def mock_env(tmp_path):
    """Provide a mock Odoo environment suitable for all tool handlers.

    Includes:
      - env.cr.dbname, env.cr.execute, env.cr.fetchall, env.cr.dictfetchall,
        env.cr.description, env.cr.rowcount
      - env['ir.config_parameter'].sudo().get_param / set_param
      - env['ir.module.module'].sudo() with search/search_count
      - env.uid, env.context
      - ICP params are backed by a real dict so set_param / get_param work.
      - A temporary audit log path is pre-configured to avoid file-system side
        effects outside tmp_path.
    """
    env = MagicMock()

    # --- Cursor ---
    env.cr.dbname = "test_db"
    env.cr.rowcount = 0

    # --- uid / context ---
    env.uid = 1
    env.context = {}

    # --- ir.config_parameter (ICP) backed by a real dict ---
    _icp_store = {
        "mcp.audit_enabled": "True",
        "mcp.audit_log_path": str(tmp_path / "mcp_audit.log"),
        "mcp.command_max_timeout": "600",
        "mcp.max_read_size_mb": "10",
        "mcp.max_write_size_mb": "50",
        "mcp.max_result_rows": "1000",
        "mcp.phone_home_url": "",
        "mcp.phone_home_retry_count": "3",
        "mcp.phone_home_timeout": "5",
        "mcp.server_port": "8768",
    }

    icp_sudo = MagicMock()

    def _get_param(key, default=False):
        return _icp_store.get(key, default)

    def _set_param(key, value):
        _icp_store[key] = value

    icp_sudo.get_param = MagicMock(side_effect=_get_param)
    icp_sudo.set_param = MagicMock(side_effect=_set_param)

    icp_model = MagicMock()
    icp_model.sudo.return_value = icp_sudo

    # --- ir.module.module ---
    module_sudo = MagicMock()
    module_model = MagicMock()
    module_model.sudo.return_value = module_sudo

    # --- __getitem__ dispatch ---
    _model_dispatch = {
        "ir.config_parameter": icp_model,
        "ir.module.module": module_model,
    }

    def _env_getitem(key):
        if key in _model_dispatch:
            return _model_dispatch[key]
        return MagicMock()

    env.__getitem__ = MagicMock(side_effect=_env_getitem)

    # Expose helpers on the fixture for test convenience
    env._icp_store = _icp_store
    env._icp_sudo = icp_sudo
    env._module_sudo = module_sudo
    env._tmp_path = tmp_path

    return env


@pytest.fixture
def temp_audit_log(tmp_path):
    """Create a temporary audit log file path."""
    log_file = tmp_path / "audit.log"
    log_file.touch()
    return str(log_file)
