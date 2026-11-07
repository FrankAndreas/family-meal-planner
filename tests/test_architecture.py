"""The layering: the *_api modules are the HTTP layer (routes); everything else is used by them and knows nothing of
HTTP, so it also works outside a request (the importer runs in a thread of its own)."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "backend" / "app"
# The HTTP layer besides the routers: the app itself, the login dependencies, and the routes' error answers
HTTP_LAYER = {"main", "auth", "http_errors"}
WEB_FRAMEWORKS = {"fastapi", "starlette"}


def _imports(source: str) -> set[str]:
    """The app modules (by name, however imported) and the top-level packages a module imports, also inside
    functions."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".") if node.module else []
            if node.level == 0 and parts[:1] == ["app"]:
                parts = parts[1:]
            elif node.level == 0:
                found.add(parts[0])
                continue
            if parts:
                found.add(parts[0])
            else:
                # "from . import x" / "from app import x": the names are the modules
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                found.add(parts[1] if parts[0] == "app" and len(parts) > 1 else parts[0])
    return found


def _modules() -> dict[str, set[str]]:
    return {path.stem: _imports(path.read_text()) for path in APP.rglob("*.py") if "migrations" not in path.parts}


def _http(name: str) -> bool:
    return name.endswith("_api") or name in HTTP_LAYER


def test_imports_seen_in_every_form():
    source = """
from . import plan_api
from .recipes_api import Votes
from app import shopping_api
from app.inbox_api import raw_path
import app.users_api
from starlette.exceptions import HTTPException
def later():
    from .use_up_api import fit
"""
    assert {"plan_api", "recipes_api", "shopping_api", "inbox_api", "users_api", "use_up_api", "starlette"} <= _imports(
        source
    )


def test_no_module_uses_a_router():
    """Shared code lives in modules without routes; a router is only included by main."""
    wrong = {
        name: sorted(i for i in imports if i.endswith("_api"))
        for name, imports in _modules().items()
        if name != "main" and any(i.endswith("_api") for i in imports)
    }
    assert wrong == {}


def test_only_the_http_layer_knows_http():
    """Neither the web framework nor anything of the HTTP layer (e.g. api_error) outside it."""
    modules = _modules()
    wrong = {
        name: sorted(i for i in imports if i in WEB_FRAMEWORKS or (i in modules and _http(i)))
        for name, imports in modules.items()
        if not _http(name)
    }
    assert {name: found for name, found in wrong.items() if found} == {}
