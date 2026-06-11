import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.db.encrypted_string import EncryptedString


class IntegrationProvider(StrEnum):
    QUICKBOOKS = "quickbooks"
    JOBBER = "jobber"
    HOUSECALL_PRO = "housecall_pro"
    STRIPE = "stripe"
    XERO = "xero"
    LMN = "lmn"
    HUBSPOT = "hubspot"
    GUSTO = "gusto"
    SERVICETITAN = "servicetitan"
    ASPIRE = "aspire"
    FRESHBOOKS = "freshbooks"
    SAGE = "sage"
    WAVE = "wave"
    ZOHO_BOOKS = "zoho_books"
    NETSUITE = "netsuite"
    SERVICEM8 = "servicem8"
    JOB_NIMBUS = "job_nimbus"
    FIELD_PULSE = "field_pulse"
    PAYPAL = "paypal"
    SQUARE = "square"
    SALESFORCE = "salesforce"
    PIPEDRIVE = "pipedrive"
    MONDAY = "monday"
    ADP = "adp"
    PAYCHEX = "paychex"
    RIPPLING = "rippling"
    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK_CALENDAR = "outlook_calendar"
    SORTLY = "sortly"
    FLEETIO = "fleetio"
    ROUTE4ME = "route4me"
    ONFLEET = "onfleet"
    TWILIO = "twilio"
    SLACK = "slack"


class ImportType(StrEnum):
    CUSTOMERS = "customers"
    JOBS = "jobs"
    WORK_ORDERS = "work_orders"
    INVOICES = "invoices"
    PAYMENTS = "payments"
    EMPLOYEES = "employees"
    ASSETS = "assets"
    SCHEDULE_EVENTS = "schedule_events"
    LOCATIONS = "locations"


class ImportStatus(StrEnum):
    PENDING = "pending"
    SCANNING = "scanning"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class ImportResult(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    ROLLED_BACK = "rolled_back"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"
    ERROR = "error"
    PENDING = "pending"


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    tenant = Column(String(255), nullable=False)
    connection_status = Column(SAEnum(ConnectionStatus), default=ConnectionStatus.PENDING, nullable=False)  # type: ignore[var-annotated]
    access_token = Column(EncryptedString(4000), nullable=True)  # type: ignore[var-annotated]
    refresh_token = Column(EncryptedString(4000), nullable=True)  # type: ignore[var-annotated]
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "provider", "tenant", name="uq_connection_company_provider_tenant"),
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="SET NULL"), nullable=True)
    provider = Column(String(50), nullable=False)
    import_type = Column(SAEnum(ImportType), nullable=False)  # type: ignore[var-annotated]
    status = Column(SAEnum(ImportStatus), default=ImportStatus.PENDING, nullable=False)  # type: ignore[var-annotated]
    progress_pct = Column(Float, default=0.0)
    total_records = Column(Integer, default=0)
    imported_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    connection = relationship("IntegrationConnection", backref="import_jobs")


class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    import_job_id = Column(UUID(as_uuid=True), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=True)
    external_system = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)
    internal_id = Column(String(255), nullable=True)
    entity_type = Column(SAEnum(ImportType), nullable=False)  # type: ignore[var-annotated]
    result = Column(SAEnum(ImportResult), default=ImportResult.SUCCESS, nullable=False)  # type: ignore[var-annotated]
    error_message = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    import_job = relationship("ImportJob", backref="import_logs")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "external_system", "external_id", "entity_type",
            name="uq_import_logs_dedup",
        ),
    )


class MappingRule(Base):
    __tablename__ = "mapping_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    source_field = Column(String(255), nullable=False)
    destination_field = Column(String(255), nullable=False)
    transformation_rule = Column(Text, nullable=True)
    entity_type = Column(SAEnum(ImportType), nullable=False)  # type: ignore[var-annotated]
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "company_id", "provider", "source_field", "destination_field", "entity_type",
            name="uq_mapping_rule",
        ),
    )
