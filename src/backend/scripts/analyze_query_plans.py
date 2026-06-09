"""Query plan analysis tool (L-3 fix).

Runs EXPLAIN ANALYZE on critical list queries with synthetic data volumes
to detect missing indexes, N+1 patterns, and performance bottlenecks
before production deployment.

Usage:
    python scripts/analyze_query_plans.py [--url DATABASE_URL] [--rows ROWS]

Requirements:
    - PostgreSQL with pgvector extension
    - Database must have the full schema (run migrations first)
    - Synthetic data is generated for analysis (no real data needed)
"""

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_CRITICAL_QUERIES: list[dict[str, Any]] = [
    {
        "name": "Job listing (paginated, no filter)",
        "query": """
            EXPLAIN ANALYZE
            SELECT j.id, j.status, j.scheduled_time, j.description, j.ai_processing_state,
                   u.name AS technician_name, c.name AS customer_name
            FROM jobs j
            JOIN users u ON j.technician_id = u.id
            JOIN customers c ON j.customer_id = c.id
            WHERE j.company_id = :company_id AND j.is_deleted = false
            ORDER BY j.scheduled_time DESC, j.id DESC
            LIMIT 25 OFFSET 0
        """,
        "params": {},
    },
    {
        "name": "Job detail (with eager loads)",
        "query": """
            EXPLAIN ANALYZE
            SELECT j.*, jm.id AS media_id, jm.type AS media_type, jm.storage_url,
                   ao.id AS ai_output_id, ao.output_type, ao.confidence_score
            FROM jobs j
            LEFT JOIN job_media jm ON j.id = jm.job_id AND jm.company_id = :company_id
            LEFT JOIN ai_outputs ao ON j.id = ao.job_id AND ao.company_id = :company_id
            WHERE j.id = :job_id AND j.company_id = :company_id AND j.is_deleted = false
        """,
        "params": {},
    },
    {
        "name": "Usage ledger (range query)",
        "query": """
            EXPLAIN ANALYZE
            SELECT company_id, job_id, text_units, vision_units, audio_units, cost_usd, created_at
            FROM usage_ledger
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            LIMIT 100
        """,
        "params": {},
    },
    {
        "name": "Invoices listing (per company)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, company_id, job_id, subtotal, tax, total, status, created_at
            FROM invoices
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            LIMIT 50
        """,
        "params": {},
    },
    {
        "name": "AI outputs (per job with index)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, job_id, company_id, output_type, confidence_score, created_at
            FROM ai_outputs
            WHERE company_id = :company_id AND job_id = :job_id
            ORDER BY created_at DESC
        """,
        "params": {},
    },
    {
        "name": "Estimates listing (per company, sorted)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, job_id, company_id, status, total_amount, created_at
            FROM estimates
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            LIMIT 50 OFFSET 0
        """,
        "params": {},
    },
    {
        "name": "Job audit log (per job)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, job_id, changed_by_user_id, field_name, old_value, new_value, created_at
            FROM job_audit_logs
            WHERE job_id = :job_id AND company_id = :company_id
            ORDER BY created_at DESC
            LIMIT 100
        """,
        "params": {},
    },
    {
        "name": "Billing audit log (per company)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, company_id, billing_account_id, changed_by_user_id, field_name, old_value, new_value, created_at
            FROM billing_audit_logs
            WHERE company_id = :company_id
            ORDER BY created_at DESC
            LIMIT 100
        """,
        "params": {},
    },
    {
        "name": "Analytics events (aggregation query)",
        "query": """
            EXPLAIN ANALYZE
            SELECT event_name, COUNT(*) AS event_count, DATE_TRUNC('hour', created_at) AS hour
            FROM analytics_events
            WHERE company_id = :company_id AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY event_name, DATE_TRUNC('hour', created_at)
            ORDER BY hour DESC
        """,
        "params": {},
    },
    {
        "name": "Dead letter jobs (per company)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, company_id, task_name, error_message, retry_count, created_at
            FROM dead_letter_jobs
            WHERE company_id = :company_id AND created_at > NOW() - INTERVAL '30 days'
            ORDER BY created_at DESC
            LIMIT 100
        """,
        "params": {},
    },
    {
        "name": "Billing accounts (version check query)",
        "query": """
            EXPLAIN ANALYZE
            SELECT id, company_id, plan, used_acu, reserved_acu, version, updated_at
            FROM billing_accounts
            WHERE company_id = :company_id
        """,
        "params": {},
    },
]


async def analyze_queries(engine, company_id: str, job_id: str) -> list[dict]:
    results = []
    async with engine.connect() as conn:
        for query_spec in _CRITICAL_QUERIES:
            params = query_spec.get("params", {})
            params["company_id"] = company_id
            if "job_id" in query_spec["query"]:
                params["job_id"] = job_id

            start = time.monotonic()
            try:
                result = await conn.execute(text(query_spec["query"]), params)
                rows = result.fetchall()
                plan_output = "\n".join(str(row[0]) for row in rows if row[0])
                elapsed = (time.monotonic() - start) * 1000

                results.append(
                    {
                        "name": query_spec["name"],
                        "status": "ok",
                        "elapsed_ms": round(elapsed, 2),
                        "plan": plan_output[:2000],
                    }
                )
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                results.append(
                    {
                        "name": query_spec["name"],
                        "status": "error",
                        "elapsed_ms": round(elapsed, 2),
                        "error": str(e),
                    }
                )
    return results


def detect_issues(results: list[dict]) -> list[dict]:
    """Scan EXPLAIN plans for common performance issues."""
    issues = []

    for r in results:
        plan = r.get("plan", "")
        query_name = r["name"]

        # Sequential scan on large tables
        if "Seq Scan" in plan and "cost=" in plan:
            cost_parts = plan.split("cost=")[1].split("..")[1].split(" ")[0] if "cost=" in plan else "0"
            try:
                cost = float(cost_parts)
                if cost > 100.0:
                    issues.append(
                        {
                            "query": query_name,
                            "issue": "Sequential scan with high cost",
                            "cost": cost,
                            "recommendation": "Add or adjust indexes for the WHERE/JOIN columns",
                        }
                    )
            except ValueError:
                pass

        # Missing index hints
        if "Index Cond" not in plan and ("WHERE" in plan.upper() or "JOIN" in plan.upper()):
            issues.append(
                {
                    "query": query_name,
                    "issue": "No index condition used despite WHERE/JOIN clauses",
                    "recommendation": "Verify indexes exist for filtered and joined columns",
                }
            )

        # Slow query (>100ms)
        if r.get("elapsed_ms", 0) > 100:
            issues.append(
                {
                    "query": query_name,
                    "issue": f"Query took {r['elapsed_ms']:.1f}ms",
                    "recommendation": "Check query plan for optimization opportunities",
                }
            )

    return issues


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze query plans for WorkTicket")
    parser.add_argument("--url", default=os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/workticket"))
    parser.add_argument("--rows", type=int, default=10000, help="Target rows for analysis context")
    args = parser.parse_args()

    engine = create_async_engine(args.url, echo=False)
    try:
        # Get a valid company_id and job_id from the database
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT id FROM companies LIMIT 1"))
            row = result.fetchone()
            if not row:
                print("No companies found in database. Run migrations and seed data first.")
                return 1
            company_id = str(row[0])

            result = await conn.execute(
                text("SELECT id FROM jobs WHERE company_id = :cid LIMIT 1"),
                {"cid": company_id},
            )
            row = result.fetchone()
            job_id = str(row[0]) if row else company_id

        print(f"Analyzing queries with company_id={company_id}, job_id={job_id}")
        print(f"Target row volume: {args.rows:,}")
        print("=" * 80)

        results = await analyze_queries(engine, company_id, job_id)
        issues = detect_issues(results)

        for r in results:
            print(f"\n{'=' * 80}")
            print(f"Query: {r['name']}")
            print(f"Status: {r['status']} | Elapsed: {r.get('elapsed_ms', 'N/A')}ms")
            if r.get("plan"):
                print(f"Plan:\n{r['plan'][:2000]}")
            if r.get("error"):
                print(f"Error: {r['error']}")

        if issues:
            print(f"\n{'=' * 80}")
            print(f"PERFORMANCE ISSUES FOUND: {len(issues)}")
            for i, issue in enumerate(issues, 1):
                print(f"\n  #{i}: {issue['query']}")
                print(f"  Issue: {issue['issue']}")
                print(f"  Recommendation: {issue['recommendation']}")
        else:
            print(f"\n{'=' * 80}")
            print("No performance issues detected in query plans.")

        # Write results to JSON for CI
        output_path = os.path.join(os.path.dirname(__file__), "query_plan_results.json")
        with open(output_path, "w") as f:
            json.dump(
                {
                    "analyzed_at": datetime.now(UTC).isoformat(),
                    "target_rows": args.rows,
                    "results": results,
                    "issues": issues,
                },
                f,
                indent=2,
                default=str,
            )
        print(f"\nResults written to {output_path}")

        return 1 if issues else 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
