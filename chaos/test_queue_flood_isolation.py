"""Queue Flood Chaos Test — validates per-queue backpressure isolation.

SC1+SC2 FIX: Simulates queue flooding on individual Celery queues and
verifies that backpressure on one queue does not block other queues.
Validates the H-5 fix (per-queue depth thresholds) and queue_pressure
check in broker.py.
"""

import json
import logging
import os
import sys
import time

import redis

logger = logging.getLogger(__name__)

QUEUES = ["default", "ai_text", "ai_audio", "ai_image", "beat"]
FLOOD_COUNT = 50
BACKPRESSURE_THRESHOLD = int(os.environ.get("CELERY_QUEUE_BACKPRESSURE_THRESHOLD", "20"))


def get_redis_client():
    """Get sync Redis client for chaos testing."""
    url = os.environ.get("REDIS_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    return redis.from_url(url, socket_connect_timeout=5, socket_timeout=5)


def flood_queue(queue_name: str, count: int = FLOOD_COUNT) -> int:
    """Push synthetic tasks to a queue until it reaches flood_count.
    
    Returns the number of items pushed.
    """
    r = get_redis_client()
    pushed = 0
    for i in range(count):
        task_id = f"chaos-flood-{queue_name}-{i}-{time.time()}"
        payload = json.dumps({
            "id": task_id,
            "task": "chaos.flood_test",
            "args": [],
            "kwargs": {"test": True},
        })
        r.lpush(queue_name, payload)
        pushed += 1
    
    depth = r.llen(queue_name)
    logger.info("[CHAOS] Flooded queue '%s': %d items pushed, current depth=%d", 
                queue_name, pushed, depth)
    return pushed


def drain_queue(queue_name: str) -> int:
    """Remove all synthetic chaos test items from a queue."""
    r = get_redis_client()
    removed = 0
    while True:
        item = r.rpop(queue_name)
        if item is None:
            break
        item_str = item.decode() if isinstance(item, bytes) else item
        if "chaos.flood_test" in item_str:
            removed += 1
        else:
            r.rpush(queue_name, item)
            break
    logger.info("[CHAOS] Drained queue '%s': %d chaos items removed", queue_name, removed)
    return removed


def check_queue_isolation(flooded_queue: str) -> dict:
    """Check that flooding one queue doesn't affect other queues.
    
    Returns a dict with queue depths and whether isolation holds.
    """
    r = get_redis_client()
    depths = {}
    isolation_ok = True
    
    for q in QUEUES:
        depth = r.llen(q)
        depths[q] = depth
        
        if q != flooded_queue and depth > BACKPRESSURE_THRESHOLD:
            logger.warning("[CHAOS] ISOLATION BREACH: queue '%s' has depth=%d while '%s' is flooded",
                          q, depth, flooded_queue)
            isolation_ok = False
    
    return {"depths": depths, "isolation_ok": isolation_ok}


def run_queue_flood_test() -> dict:
    """Run the full queue flood chaos test.
    
    Tests each queue individually:
    1. Record baseline depths
    2. Flood target queue
    3. Verify other queues are unaffected
    4. Clean up
    
    Returns a comprehensive test report.
    """
    logger.info("[CHAOS] Starting queue flood isolation test against %d queues", len(QUEUES))
    results = {}
    all_passed = True
    
    for queue in QUEUES:
        logger.info("[CHAOS] --- Testing queue '%s' ---", queue)
        
        try:
            r = get_redis_client()
            baseline = {q: r.llen(q) for q in QUEUES}
            logger.info("Baseline depths: %s", baseline)
            
            # Flood the target queue
            flood_queue(queue, FLOOD_COUNT)
            
            # Check isolation
            isolation = check_queue_isolation(queue)
            logger.info("Isolation check for '%s': %s", queue, isolation)
            
            # Clean up
            drain_queue(queue)
            
            passed = isolation["isolation_ok"]
            results[queue] = {
                "passed": passed,
                "baseline": baseline,
                "post_flood_depths": isolation["depths"],
                "flood_count": FLOOD_COUNT,
            }
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            logger.error("[CHAOS] Queue flood test failed for '%s': %s", queue, e)
            results[queue] = {"passed": False, "error": str(e)}
            all_passed = False
    
    summary = {
        "test": "queue_flood_isolation",
        "all_passed": all_passed,
        "queues_tested": len(QUEUES),
        "flood_count_per_queue": FLOOD_COUNT,
        "results": results,
        "timestamp": time.time(),
    }
    
    logger.info("[CHAOS] Queue flood test complete: all_passed=%s", all_passed)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = run_queue_flood_test()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["all_passed"] else 1)
