"""Celery Worker Autoscaler — monitors queue depth and adjusts replica count.

Usage:
    python ops/scripts/celery_autoscaler.py [--interval 30] [--dry-run]

Scales Celery workers based on queue depth thresholds using Docker Swarm
or Kubernetes APIs. Designed to run as a sidecar or cron job.

Queue depth → desired replicas mapping:
  0-10:   min_replicas
  11-50:  min_replicas + 1
  51-100: mid_replicas
  101+:   max_replicas

Configuration (environment variables):
  CELERY_AUTOSCALE_INTERVAL     — check interval in seconds (default: 30)
  CELERY_AUTOSCALE_DRY_RUN     — if true, only log (default: false)
  CELERY_TEXT_MIN/MAX_REPLICAS  — min/max for ai_text queue (default: 2/10)
  CELERY_IMAGE_MIN/MAX_REPLICAS — min/max for ai_image queue (default: 2/8)
  CELERY_AUDIO_MIN/MAX_REPLICAS — min/max for ai_audio queue (default: 2/6)
  CELERY_DEFAULT_MIN/MAX_REPLICAS — min/max for default queue (default: 1/5)
"""

import os
import sys
import time
import json
import logging
import subprocess
import argparse
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("celery-autoscaler")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_THRESHOLDS = {
    "ai_text":    {"low": 10, "mid": 50, "min": int(os.getenv("CELERY_TEXT_MIN_REPLICAS", "2")), "max": int(os.getenv("CELERY_TEXT_MAX_REPLICAS", "10"))},
    "ai_image":   {"low": 10, "mid": 50, "min": int(os.getenv("CELERY_IMAGE_MIN_REPLICAS", "2")), "max": int(os.getenv("CELERY_IMAGE_MAX_REPLICAS", "8"))},
    "ai_audio":   {"low": 10, "mid": 50, "min": int(os.getenv("CELERY_AUDIO_MIN_REPLICAS", "2")), "max": int(os.getenv("CELERY_AUDIO_MAX_REPLICAS", "6"))},
    "default":    {"low": 10, "mid": 50, "min": int(os.getenv("CELERY_DEFAULT_MIN_REPLICAS", "1")), "max": int(os.getenv("CELERY_DEFAULT_MAX_REPLICAS", "5"))},
}


def _get_queue_depths() -> dict[str, int]:
    """Query Redis for current queue depths."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=2, decode_responses=True)
        depths = {}
        for queue in QUEUE_THRESHOLDS:
            depth = r.llen(queue) or 0
            depths[queue] = depth
        r.close()
        return depths
    except Exception as e:
        logger.error("Failed to query Redis: %s", e)
        return {}


def _desired_replicas(queue: str, depth: int, config: dict) -> int:
    """Calculate desired replica count based on queue depth."""
    if depth <= config["low"]:
        return config["min"]
    elif depth <= config["mid"]:
        return config["min"] + 1
    elif depth <= config["mid"] * 2:
        return max(config["min"] + 2, (config["min"] + config["max"]) // 2)
    return config["max"]


def _scale_docker_swarm(queue: str, replicas: int) -> bool:
    """Scale Docker Swarm service by queue name."""
    service_map = {
        "ai_text": "workticket_celery-worker-text",
        "ai_image": "workticket_celery-worker-image",
        "ai_audio": "workticket_celery-worker-audio",
        "default": "workticket_celery-worker-default",
    }
    service = service_map.get(queue)
    if not service:
        logger.warning("No Docker service mapping for queue %s", queue)
        return False
    try:
        result = subprocess.run(
            ["docker", "service", "scale", f"{service}={replicas}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("Scaled %s to %d replicas", service, replicas)
            return True
        logger.error("Failed to scale %s: %s", service, result.stderr)
        return False
    except FileNotFoundError:
        logger.warning("Docker not found — cannot scale via Docker Swarm")
        return False
    except Exception as e:
        logger.error("Error scaling %s: %s", service, e)
        return False


def _scale_k8s(queue: str, replicas: int) -> bool:
    """Scale Kubernetes deployment by queue name."""
    deployment_map = {
        "ai_text": "celery-worker-text",
        "ai_image": "celery-worker-image",
        "ai_audio": "celery-worker-audio",
        "default": "celery-worker-default",
    }
    deployment = deployment_map.get(queue)
    if not deployment:
        logger.warning("No K8s deployment mapping for queue %s", queue)
        return False
    try:
        result = subprocess.run(
            ["kubectl", "scale", "deployment", deployment,
             f"--replicas={replicas}", "--namespace=workticket"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("Scaled K8s deployment %s to %d replicas", deployment, replicas)
            return True
        logger.error("Failed to scale K8s %s: %s", deployment, result.stderr)
        return False
    except FileNotFoundError:
        logger.warning("kubectl not found — cannot scale via Kubernetes")
        return False
    except Exception as e:
        logger.error("Error scaling K8s %s: %s", deployment, e)
        return False


def _get_current_replicas_k8s(deployment: str) -> Optional[int]:
    """Get current replica count from Kubernetes."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "deployment", deployment,
             "--namespace=workticket", "-o", "jsonpath={.spec.replicas}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except Exception:
        pass
    return None


def _emit_autoscale_metric(queue: str, desired: int, current: int, depth: int):
    """Emit Prometheus-compatible metric for autoscale decisions."""
    print(f"# HELP celery_autoscaler_desired_replicas Desired replica count per queue")
    print(f"# TYPE celery_autoscaler_desired_replicas gauge")
    print(f"celery_autoscaler_desired_replicas{{queue=\"{queue}\",current=\"{current}\"}} {desired}")
    print(f"celery_queue_depth{{queue=\"{queue}\"}} {depth}")


def main():
    parser = argparse.ArgumentParser(description="Celery Worker Autoscaler")
    parser.add_argument("--interval", type=int, default=int(os.getenv("CELERY_AUTOSCALE_INTERVAL", "30")),
                        help="Check interval in seconds")
    parser.add_argument("--dry-run", action="store_true", default=os.getenv("CELERY_AUTOSCALE_DRY_RUN", "").lower() in ("true", "1"),
                        help="Log only, do not scale")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--emit-metrics", action="store_true", help="Emit Prometheus metrics")
    args = parser.parse_args()

    logger.info("Celery Autoscaler starting (interval=%ds, dry_run=%s)", args.interval, args.dry_run)

    while True:
        depths = _get_queue_depths()
        if not depths:
            logger.warning("No queue depths retrieved — will retry")

        for queue, config in QUEUE_THRESHOLDS.items():
            depth = depths.get(queue, 0)
            desired = _desired_replicas(queue, depth, config)

            if args.emit_metrics:
                _emit_autoscale_metric(queue, desired, config["min"], depth)

            if desired == config["min"]:
                continue  # already at minimum, no action needed

            if args.dry_run:
                logger.info("[DRY RUN] Queue %s depth=%d → desired=%d replicas", queue, depth, desired)
                continue

            scaled = _scale_docker_swarm(queue, desired)
            if not scaled:
                scaled = _scale_k8s(queue, desired)

            if not scaled:
                logger.warning("No scaling backend available for queue %s", queue)

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
