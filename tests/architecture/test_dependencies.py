import ast
from pathlib import Path

FORBIDDEN_DOMAIN_IMPORTS = frozenset({"fastapi", "next", "sqlalchemy"})


def test_domain_has_no_framework_dependencies() -> None:
    # Given
    domain_files = Path("packages/domain").glob("**/*.py")

    # When
    imported_roots = {
        alias.name.partition(".")[0]
        for path in domain_files
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }

    # Then
    assert imported_roots.isdisjoint(FORBIDDEN_DOMAIN_IMPORTS)
