"""The layering: the *_api modules are the HTTP layer (routes); everything else is used by them and knows nothing of
HTTP, so it also works outside a request (the importer runs in a thread of its own)."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "backend" / "app"
# The HTTP layer besides the routers: the app itself, the login dependencies, and the error answers
HTTP_LAYER = {"main", "auth", "errors"}


def _imports(path: Path) -> set[str]:
    """The app modules and the top-level packages a module imports (also inside functions)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1 and node.module:
                found.add(node.module.split(".")[0])
            elif node.level == 1:
                found.update(alias.name for alias in node.names)
            elif node.module:
                found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
    return found


def _modules() -> dict[str, set[str]]:
    return {path.stem: _imports(path) for path in APP.glob("*.py")}


def test_no_module_uses_a_router():
    """Shared code lives in modules without routes; a router is only included by main."""
    wrong = {
        name: sorted(i for i in imports if i.endswith("_api"))
        for name, imports in _modules().items()
        if name != "main" and any(i.endswith("_api") for i in imports)
    }
    assert wrong == {}


def test_only_the_http_layer_knows_fastapi():
    wrong = sorted(
        name
        for name, imports in _modules().items()
        if "fastapi" in imports and not name.endswith("_api") and name not in HTTP_LAYER
    )
    assert wrong == []
