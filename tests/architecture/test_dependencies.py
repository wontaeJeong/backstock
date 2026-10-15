import ast
from pathlib import Path

FORBIDDEN_DOMAIN_IMPORTS = frozenset({"fastapi", "next", "sqlalchemy"})
FORBIDDEN_STRATEGY_IMPORTS = frozenset({"fastapi", "next", "sqlalchemy", "apps"})


def _imported_roots(package: str) -> set[str]:
    files = Path(package).glob("**/*.py")
    return {
        alias.name.partition(".")[0]
        for path in files
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }


def test_domain_has_no_framework_dependencies() -> None:
    assert _imported_roots("packages/domain").isdisjoint(FORBIDDEN_DOMAIN_IMPORTS)


def test_strategy_has_no_framework_or_broker_dependencies() -> None:
    assert _imported_roots("packages/strategy").isdisjoint(FORBIDDEN_STRATEGY_IMPORTS)
