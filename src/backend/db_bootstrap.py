"""Bootstrap database: create all tables from models and stamp alembic at head."""
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command

# Create all tables from SQLAlchemy models
from app.database import Base
from app.ai.audit import AIAuditLog
from app.analytics.events import AnalyticsEvent
from app.billing.dead_letter import DeadLetterJob
from app.billing.idempotency import IdempotencyKey
from app.billing.models import AIJobEstimate, BillingAccount, Invoice, UsageLedger, StripeWebhookEvent
from app.billing.user_quota import UserDailyUsage
from app.estimates.audit import EstimateAuditSnapshot
from app.estimates.models import (
    CompanyPricingBrain, Estimate, EstimateLineItem, HistoricalJobData, Service,
)
from app.jobs.models import *
from app.tracing.models import ExecutionTrace

engine = create_engine(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
Base.metadata.create_all(engine)
print("All tables created from models")

# Stamp alembic at head
alembic_cfg = Config("/app/alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("+asyncpg", ""))
command.stamp(alembic_cfg, "head")
print("Alembic stamped at head")
