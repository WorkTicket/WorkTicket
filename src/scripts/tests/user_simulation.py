#!/usr/bin/env python3
"""
Real User Behavior Simulation.

Simulates:
- slow users (long sessions, think time between actions)
- burst users (spam clicking, rapid-fire requests)
- idle users (creates job, walks away)
- retry-heavy users (failing requests, retry loops)
- mixed workload (audio + vision + text simultaneously)

Usage:
    python scripts/tests/user_simulation.py [--users 10] [--duration 120] [--base-url http://localhost:8000]
"""

import asyncio
import random
import time
import statistics
import argparse
from uuid import uuid4
import httpx

BACKEND_URL = "http://localhost:8000"

USER_PROFILES = {
    "slow": {"weight": 30, "think_time": (5, 15), "batch_size": (1, 3)},
    "burst": {"weight": 20, "think_time": (0.1, 0.5), "batch_size": (5, 15)},
    "idle": {"weight": 20, "think_time": (20, 60), "batch_size": (1, 2)},
    "retry": {"weight": 15, "think_time": (1, 3), "batch_size": (1, 3)},
    "mixed": {"weight": 15, "think_time": (2, 8), "batch_size": (2, 5)},
}


class SimulatedUser:
    def __init__(self, user_id: str, profile: str):
        self.user_id = user_id
        self.profile = profile
        self.config = USER_PROFILES[profile]
        self.jobs_created = 0
        self.jobs_completed = 0
        self.errors = 0
        self.total_latency = 0

    async def run(self, client: httpx.AsyncClient, duration_seconds: int):
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            batch_size = random.randint(*self.config["batch_size"])
            for _ in range(batch_size):
                await self._do_job(client)

            if self.profile == "retry" and self.jobs_created > 0 and random.random() < 0.3:
                await self._retry_loop(client)

            think = random.uniform(*self.config["think_time"])
            await asyncio.sleep(think)

        return {
            "user_id": self.user_id,
            "profile": self.profile,
            "jobs_created": self.jobs_created,
            "jobs_completed": self.jobs_completed,
            "errors": self.errors,
            "avg_latency": round(self.total_latency / max(self.jobs_created, 1), 2),
        }

    async def _do_job(self, client: httpx.AsyncClient):
        job_id = str(uuid4())
        payload = self._generate_payload()

        start = time.monotonic()
        try:
            resp = await client.post(
                f"{BACKEND_URL}/ai/process-job/{job_id}",
                json=payload,
                timeout=30,
            )
            self.jobs_created += 1
            if resp.status_code == 200:
                self.jobs_completed += 1
            else:
                self.errors += 1
            latency = (time.monotonic() - start) * 1000
            self.total_latency += latency
        except Exception:
            self.errors += 1

    async def _retry_loop(self, client: httpx.AsyncClient):
        for _ in range(random.randint(2, 5)):
            await self._do_job(client)
            await asyncio.sleep(random.uniform(0.2, 0.8))

    def _generate_payload(self) -> dict:
        trade = random.choice(["hvac", "plumbing", "electrical", "general"])
        has_audio = random.random() < 0.4
        has_images = random.random() < 0.5

        payload = {
            "description": f"User {self.user_id[:8]} [{self.profile}]: {trade} issue - needs diagnosis",
            "trade_type": trade,
        }
        if has_audio:
            payload["audio_url"] = f"https://example.com/audio/{uuid4()}.m4a"
        if has_images:
            payload["image_urls"] = [f"https://example.com/img/{uuid4()}.jpg" for _ in range(random.randint(1, 3))]
        return payload


async def run_simulation(num_users: int, duration_seconds: int):
    print(f"\n{'='*70}")
    print(f"  REAL USER SIMULATION")
    print(f"  Users: {num_users} | Duration: {duration_seconds}s")
    print(f"{'='*70}")
    print(f"  Profiles:")
    for profile, cfg in USER_PROFILES.items():
        count = max(1, num_users * cfg["weight"] // 100)
        print(f"    - {profile}: {count} users (think: {cfg['think_time']}s, batch: {cfg['batch_size']})")
    print(f"{'='*70}\n")

    client = httpx.AsyncClient(timeout=30)
    users = []
    user_id_counter = 0

    for profile, cfg in USER_PROFILES.items():
        count = max(1, num_users * cfg["weight"] // 100)
        for _ in range(count):
            uid = f"sim-user-{user_id_counter:04d}"
            user_id_counter += 1
            users.append(SimulatedUser(uid, profile))

    print(f"  Spawning {len(users)} simulated users...\n")

    start_time = time.monotonic()
    tasks = [user.run(client, duration_seconds) for user in users]
    results = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start_time

    await client.aclose()

    total_created = sum(r["jobs_created"] for r in results)
    total_completed = sum(r["jobs_completed"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    print(f"\n{'='*70}")
    print(f"  SIMULATION RESULTS ({elapsed:.0f}s elapsed)")
    print(f"{'='*70}")
    print(f"  Total jobs created:  {total_created}")
    print(f"  Total jobs completed: {total_completed}")
    print(f"  Total errors:        {total_errors}")
    print(f"  Success rate:        {total_completed/max(total_created,1)*100:.1f}%")
    print(f"\n  Per-profile breakdown:")
    print(f"  {'Profile':<12} {'Users':<6} {'Jobs':<8} {'Errors':<8} {'Avg Lat(ms)':<12}")
    print(f"  {'-'*46}")
    by_profile = {}
    for r in results:
        p = r["profile"]
        if p not in by_profile:
            by_profile[p] = {"users": 0, "jobs": 0, "errors": 0, "latencies": []}
        by_profile[p]["users"] += 1
        by_profile[p]["jobs"] += r["jobs_created"]
        by_profile[p]["errors"] += r["errors"]
        by_profile[p]["latencies"].append(r["avg_latency"])

    for profile, data in sorted(by_profile.items()):
        avg_lat = statistics.mean(data["latencies"]) if data["latencies"] else 0
        print(f"  {profile:<12} {data['users']:<6} {data['jobs']:<8} {data['errors']:<8} {avg_lat:<12.1f}")

    print(f"{'='=70}\n")


def main():
    parser = argparse.ArgumentParser(description="Real User Simulation")
    parser.add_argument("--users", type=int, default=10, help="Number of simulated users")
    parser.add_argument("--duration", type=int, default=120, help="Simulation duration in seconds")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Backend API URL")
    args = parser.parse_args()

    global BACKEND_URL
    BACKEND_URL = args.base_url.rstrip("/")
    asyncio.run(run_simulation(args.users, args.duration))


if __name__ == "__main__":
    main()
