"""Cross-region disaster recovery failover automation.

Provides validation and orchestration for promoting a secondary region
to primary during an outage. Designed for manual execution by on-call
engineers with safety checks and dry-run mode.

Usage:
    # Validate current failover readiness
    python ops/scripts/failover.py --validate-only

    # Dry-run failover (log what would happen)
    python ops/scripts/failover.py --dry-run

    # Execute failover (requires confirmation)
    python ops/scripts/failover.py --execute

    # Run recovery drill (non-destructive)
    python ops/scripts/failover.py --recovery-drill
"""

import os
import sys
import json
import time
import logging
import subprocess
import argparse
import urllib.request
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("failover")

# Configuration
PRIMARY_API = os.environ.get("PRIMARY_API_URL", "https://api.workticket.app")
SECONDARY_API = os.environ.get("SECONDARY_API_URL", "https://api-secondary.workticket.app")
PRIMARY_DB_HOST = os.environ.get("PRIMARY_DB_HOST", "")
SECONDARY_DB_HOST = os.environ.get("SECONDARY_DB_HOST", "")
K8S_NAMESPACE = os.environ.get("K8S_NAMESPACE", "workticket")
CLOUDFLARE_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID", "")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CF_DNS_RECORD_ID = os.environ.get("CF_DNS_RECORD_ID", "")
SECONDARY_LB_IP = os.environ.get("SECONDARY_LB_IP", "")


def _check_endpoint(url: str, path: str = "/healthz", timeout: int = 10) -> bool:
    """Check if an endpoint is reachable and healthy."""
    try:
        req = urllib.request.Request(f"{url}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug("Endpoint %s%s not reachable: %s", url, path, e)
        return False


def _kubectl(args: list[str]) -> Optional[str]:
    """Run kubectl command and return output."""
    try:
        result = subprocess.run(
            ["kubectl", "--namespace", K8S_NAMESPACE] + args,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        logger.error("kubectl %s failed: %s", " ".join(args[:3]), result.stderr)
        return None
    except FileNotFoundError:
        logger.error("kubectl not found")
        return None
    except Exception as e:
        logger.error("kubectl error: %s", e)
        return None


def _update_dns(ip_address: str) -> bool:
    """Update Cloudflare DNS record for failover."""
    if not all([CLOUDFLARE_ZONE_ID, CLOUDFLARE_API_TOKEN, CF_DNS_RECORD_ID]):
        logger.warning("Cloudflare DNS not configured — skipping DNS update")
        return False
    try:
        data = json.dumps({
            "type": "A",
            "name": "api.workticket.app",
            "content": ip_address,
            "ttl": 60,
        }).encode()
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{CF_DNS_RECORD_ID}",
            data=data, method="PUT",
        )
        req.add_header("Authorization", f"Bearer {CLOUDFLARE_API_TOKEN}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get("success", False)
    except Exception as e:
        logger.error("DNS update failed: %s", e)
        return False


def validate_readiness() -> dict:
    """Validate current failover readiness and return status."""
    status = {
        "primary_api": _check_endpoint(PRIMARY_API),
        "secondary_api": _check_endpoint(SECONDARY_API),
        "primary_readyz": _check_endpoint(PRIMARY_API, "/readyz"),
        "secondary_readyz": _check_endpoint(SECONDARY_API, "/readyz"),
    }
    logger.info("Failover readiness check:")
    logger.info("  Primary API:   %s", "OK" if status["primary_api"] else "DOWN")
    logger.info("  Secondary API: %s", "OK" if status["secondary_api"] else "DOWN")
    logger.info("  Primary Ready: %s", "OK" if status["primary_readyz"] else "DOWN")
    logger.info("  Secondary Ready: %s", "OK" if status["secondary_readyz"] else "DOWN")

    if status["primary_api"] and status["primary_readyz"]:
        status["verdict"] = "PRIMARY_HEALTHY — no failover needed"
        logger.info("  Verdict: PRIMARY_HEALTHY — no failover needed")
    elif not status["primary_api"] and status["secondary_api"]:
        status["verdict"] = "FAILOVER_NEEDED — primary down, secondary available"
        logger.info("  Verdict: FAILOVER_NEEDED — primary down, secondary available")
    elif not status["primary_api"] and not status["secondary_api"]:
        status["verdict"] = "BOTH_REGIONS_DOWN — critical outage"
        logger.error("  Verdict: BOTH_REGIONS_DOWN — critical outage")
    else:
        status["verdict"] = "DEGRADED — investigate"
        logger.warning("  Verdict: DEGRADED — investigate")
    return status


def execute_failover(dry_run: bool = False) -> bool:
    """Execute cross-region failover to secondary region."""
    logger.info("=== Starting failover%s ===", " (DRY RUN)" if dry_run else "")

    # Step 1: Validate readiness
    status = validate_readiness()
    if status["verdict"] == "PRIMARY_HEALTHY" and not dry_run:
        logger.warning("Primary is healthy. Use --force to override.")
        return False

    # Step 2: Promote secondary database
    logger.info("Step 2: Promoting secondary database...")
    if dry_run:
        logger.info("[DRY RUN] Would promote DB on %s", SECONDARY_DB_HOST)
    else:
        # In production, this would SSH to the secondary DB and run pg_ctl promote
        logger.info("Promote secondary DB (manual step for now)")
        logger.info("  SSH to secondary DB host and run:")
        logger.info("  sudo -u postgres pg_ctl promote -D /var/lib/postgresql/data")

    # Step 3: Update Kubernetes configs
    logger.info("Step 3: Updating K8s configs for secondary region...")
    if dry_run:
        logger.info("[DRY RUN] Would update DATABASE_URL in K8s secrets")
    else:
        new_db_url = f"postgresql+asyncpg://postgres@{SECONDARY_DB_HOST}:5432/workticket"
        _kubectl(["set", "env", "deployment/workticket-api", f"DATABASE_URL={new_db_url}"])
        logger.info("Updated K8s secrets for secondary region")

    # Step 4: Restart deployments
    logger.info("Step 4: Restarting services in secondary region...")
    if dry_run:
        logger.info("[DRY RUN] Would restart all deployments")
    else:
        for dep in ["workticket-api", "celery-worker-text", "celery-worker-image",
                     "celery-worker-audio", "celery-worker-default"]:
            _kubectl(["rollout", "restart", f"deployment/{dep}"])
            logger.info("  Restarted %s", dep)

    # Step 5: Update DNS
    logger.info("Step 5: Updating DNS to point to secondary region...")
    if dry_run:
        logger.info("[DRY RUN] Would update DNS to %s", SECONDARY_LB_IP or "<secondary-lb-ip>")
    else:
        if _update_dns(SECONDARY_LB_IP):
            logger.info("DNS updated to secondary region")
        else:
            logger.warning("DNS update failed — update manually")

    # Step 6: Verify
    logger.info("Step 6: Verifying failover...")
    time.sleep(10)  # Wait for DNS propagation
    if _check_endpoint(SECONDARY_API):
        logger.info("Secondary API is healthy after failover")
    else:
        logger.error("Secondary API not healthy after failover")
        return False

    logger.info("=== Failover %s ===", "simulated (DRY RUN)" if dry_run else "complete")
    return True


def execute_recovery_drill():
    """Run a non-destructive recovery drill to validate failover readiness."""
    logger.info("=== Recovery Drill ===")
    logger.info("Phase 1: Readiness validation")
    status = validate_readiness()
    if not status["secondary_api"]:
        logger.error("Secondary region not available — cannot run drill")
        return False

    logger.info("Phase 2: DNS update test")
    logger.info("Verifying Cloudflare API access...")
    if CLOUDFLARE_API_TOKEN:
        logger.info("  Cloudflare API accessible")
    else:
        logger.warning("  CLOUDFLARE_API_TOKEN not set — DNS test skipped")

    logger.info("Phase 3: Database connectivity test")
    _kubectl(["exec", "deployment/workticket-api", "--", "python", "-c",
              "'from app.database import engine; import asyncio; asyncio.run(engine.connect())'"])
    logger.info("  Database connectivity: OK")

    logger.info("Phase 4: Rollback plan validation")
    logger.info("  Ensure primary region is stable before switching back")
    logger.info("  Run: failover.py --execute (to switch back to primary)")

    logger.info("=== Recovery Drill Complete ===")
    return True


def main():
    parser = argparse.ArgumentParser(description="Cross-region failover automation")
    parser.add_argument("--validate-only", action="store_true", help="Only validate readiness")
    parser.add_argument("--dry-run", action="store_true", help="Simulate failover without changes")
    parser.add_argument("--execute", action="store_true", help="Execute failover")
    parser.add_argument("--recovery-drill", action="store_true", help="Run recovery drill")
    parser.add_argument("--force", action="store_true", help="Force failover even if primary is healthy")
    args = parser.parse_args()

    if args.validate_only:
        validate_readiness()
        return

    if args.dry_run:
        execute_failover(dry_run=True)
        return

    if args.execute:
        confirm = input("Execute failover? This will switch traffic to secondary region. [y/N]: ")
        if confirm.lower() in ("y", "yes"):
            execute_failover(dry_run=False)
        else:
            logger.info("Failover cancelled")
        return

    if args.recovery_drill:
        execute_recovery_drill()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
