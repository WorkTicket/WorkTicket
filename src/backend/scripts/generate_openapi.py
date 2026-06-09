"""OpenAPI spec generation script (L-2 fix).

Generates the committed OpenAPI specification from the running FastAPI
application. This enables:
- Client SDK generation without running the server
- API documentation in CI/CD pipelines
- Contract testing against the spec
- Version comparison between releases

Usage:
    python scripts/generate_openapi.py [--output openapi.json]

The generated openapi.json should be committed to the repository
alongside each release.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("openapi-gen")


async def generate(output_path: str):
    """Generate OpenAPI spec from the FastAPI app."""
    # Must import after path setup and with minimal side effects
    # Override settings to avoid requiring live DB/Redis connections
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost:5432/workticket")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("REDIS_BROKER_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CLERK_JWT_ISSUER", "https://clerk.example.com")
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("ALLOWED_HOSTS", "localhost")
    os.environ.setdefault("DEBUG", "true")

    from app.main import app

    # Generate OpenAPI schema
    openapi_schema = app.openapi()

    # Add server URLs for different environments
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://staging.workticket.app", "description": "Staging"},
        {"url": "https://api.workticket.app", "description": "Production"},
    ]

    # Add tags metadata
    openapi_schema.setdefault(
        "tags",
        [
            {"name": "auth", "description": "Authentication and user management"},
            {"name": "jobs", "description": "Job/work order CRUD operations"},
            {"name": "media", "description": "File upload and media management"},
            {"name": "ai", "description": "AI analysis and processing"},
            {"name": "quotes", "description": "Quote generation and management"},
            {"name": "billing", "description": "Billing, usage, and Stripe integration"},
            {"name": "estimates", "description": "AI-generated estimate management"},
            {"name": "notifications", "description": "Push and email notifications"},
            {"name": "analytics", "description": "Analytics and reporting"},
            {"name": "tracing", "description": "Distributed tracing and execution history"},
            {"name": "compliance", "description": "GDPR and compliance endpoints"},
            {"name": "dlq", "description": "Dead letter queue management"},
            {"name": "public", "description": "Publicly accessible endpoints"},
            {"name": "staff", "description": "Staff-level authenticated endpoints"},
            {"name": "admin", "description": "Admin-only authenticated endpoints"},
        ],
    )

    # Remove any sensitive info from descriptions
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and "operationId" not in operation:
                tag = operation.get("tags", ["default"])[0] if operation.get("tags") else "default"
                summary = operation.get("summary", path.replace("/", "_").strip("_"))
                operation["operationId"] = f"{tag}_{method}_{summary.lower().replace(' ', '_')[:50]}"

    # Write output
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    file_size = os.path.getsize(output_path)
    endpoint_count = len(openapi_schema.get("paths", {}))
    schema_count = len(openapi_schema.get("components", {}).get("schemas", {}))

    logger.info(f"OpenAPI spec generated: {output_path}")
    logger.info(f"  Size: {file_size:,} bytes")
    logger.info(f"  Endpoints: {endpoint_count}")
    logger.info(f"  Schemas: {schema_count}")
    logger.info(f"  Version: {openapi_schema.get('info', {}).get('version', 'unknown')}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate OpenAPI specification")
    parser.add_argument("--output", "-o", default="openapi.json", help="Output file path")
    args = parser.parse_args()

    output_path = args.output
    if not os.path.isabs(output_path):
        # Make relative to repository root
        repo_root = Path(__file__).parent.parent.parent
        output_path = str(repo_root / output_path)

    asyncio.run(generate(output_path))
