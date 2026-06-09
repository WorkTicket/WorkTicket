import os
import json
import random
from locust import HttpUser, task, between, constant


class WorkTicketUser(HttpUser):
    wait_time = between(1, 5)
    token = None
    company_id = None

    def on_start(self):
        self.token = os.environ.get("LOCUST_AUTH_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @task(3)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(2)
    def get_jobs(self):
        self.client.get(
            "/api/v1/jobs?page=1&page_size=10",
            headers=self.headers,
            name="/api/v1/jobs [GET]",
        )

    @task(1)
    def get_billing_account(self):
        self.client.get(
            "/api/v1/billing/account",
            headers=self.headers,
            name="/api/v1/billing/account",
        )

    @task(1)
    def get_quota(self):
        self.client.get(
            "/api/v1/billing/quota",
            headers=self.headers,
            name="/api/v1/billing/quota",
        )

    @task(1)
    def estimate_cost(self):
        self.client.post(
            "/api/v1/billing/estimate-cost?image_count=1",
            headers=self.headers,
            name="/api/v1/billing/estimate-cost",
        )


class HealthCheckUser(HttpUser):
    wait_time = constant(1)

    @task
    def health(self):
        self.client.get("/health", name="/health [unauthed]")


class AIJobUser(HttpUser):
    wait_time = between(2, 10)

    @task
    def create_ai_job(self):
        self.client.post(
            "/api/v1/ai/process",
            json={
                "description": f"Test job {random.randint(1, 10000)}",
                "trade_type": random.choice(["hvac", "plumbing", "electrical"]),
            },
            headers={"Authorization": "Bearer test-token"},
            name="/api/v1/ai/process",
        )
