import os
import sys

_TEST_DEFAULTS = {
    "DEBUG": "true",
    "database_url": "postgresql+asyncpg://postgres:postgres@localhost:5432/workticket",
    "redis_url": "redis://localhost:6379/0",
    "redis_password": "",
    "clerk_secret_key": "clerk_test_placeholder",
    "clerk_publishable_key": "clerk_publishable_placeholder",
    "clerk_jwt_issuer": "https://clerk.example.com",
    "clerk_jwt_audience": "workticket-test",
    "r2_endpoint_url": "https://test.r2.cloudflarestorage.com",
    "r2_access_key_id": "r2_test_key_placeholder",
    "r2_secret_access_key": "r2_test_secret_placeholder",
    "stripe_secret_key": "sk_test_placeholder",
    "stripe_webhook_secret": "whsec_test_placeholder",
    "stripe_price_id": "price_test_placeholder",
    "sentry_dsn": "",
    "posthog_api_key": "",
    "metrics_access_token": "",
    "twilio_account_sid": "AC_test_placeholder",
    "twilio_auth_token": "test_auth_token_placeholder",
    "twilio_from_number": "+15005550006",
    "resend_api_key": "re_test_placeholder",
    "celery_task_signing_key": "chaos-test-signing-key-do-not-use-in-prod",
    "allowed_hosts": "localhost",
    "app_base_url": "http://localhost:3000",
    "cors_origins": "http://localhost:3000",
}
for _key, _val in _TEST_DEFAULTS.items():
    os.environ.setdefault(_key, _val)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

pytest_plugins = ["pytest_asyncio"]
