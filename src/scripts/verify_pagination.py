"""Verify pagination on all list endpoints by checking router definitions.

This static analysis script checks that all GET endpoints returning
lists have pagination parameters (page, page_size, cursor, limit)
defined in their FastAPI route signature.
"""
import ast
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
ROUTER_DIRS = [
    "app/jobs", "app/ai", "app/billing", "app/quotes", "app/estimates",
    "app/media", "app/analytics", "app/notifications", "app/tracing",
    "app/auth",
]

PAGINATION_PARAMS = {"page", "page_size", "cursor", "limit", "offset"}
SKIP_ENDPOINTS = {"/health", "/livez", "/readyz", "/metrics", "/docs", "/openapi.json"}


def check_router_file(filepath: Path) -> list[str]:
    """Check a single router file for endpoints missing pagination."""
    issues = []
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        return [f"  Syntax error: {e}"]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr'):
                decorators.append(dec.func.attr)

        is_get_route = any(d in ("get", "list", "search") for d in decorators)
        is_list_response = "List" in node.name or "list" in node.name

        if not is_get_route and not is_list_response:
            continue

        params = {a.arg for a in node.args.args if isinstance(a, ast.arg)}
        defaults = set()
        for d in node.args.defaults:
            if isinstance(d, ast.Call) and hasattr(d.func, 'id') and d.func.id == "Query":
                defaults.update(a.arg for a in d.args if isinstance(a, ast.arg))

        has_pagination = bool(PAGINATION_PARAMS & (params | defaults))

        if not has_pagination:
            route_path = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and dec.args:
                    route_path = ast.unparse(dec.args[0]) if dec.args else ""

            if route_path and route_path.strip('"') not in SKIP_ENDPOINTS:
                issues.append(
                    f"  {filepath.name}:{node.lineno} - {node.name}() "
                    f"(route {route_path})"
                )

    return issues


def main():
    issues_found = []

    for router_dir in ROUTER_DIRS:
        dirpath = BACKEND_DIR / router_dir
        if not dirpath.exists():
            continue
        for router_file in sorted(dirpath.glob("router.py")):
            issues = check_router_file(router_file)
            if issues:
                issues_found.append(f"\n{router_file.relative_to(BACKEND_DIR.parent)}:")
                issues_found.extend(issues)

    if issues_found:
        print("⚠️  Endpoints that may be missing pagination:")
        print("\n".join(issues_found))
        print("\nReview these endpoints and add page/page_size Query parameters if needed.")
    else:
        print("✅ All list endpoints appear to have pagination parameters.")


if __name__ == "__main__":
    main()
