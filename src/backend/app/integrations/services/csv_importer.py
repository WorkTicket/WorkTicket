import csv
import io
import logging

from app.integrations.canonical import (
    CanonicalAsset,
    CanonicalCustomer,
    CanonicalEmployee,
    CanonicalInvoice,
    CanonicalJob,
    CanonicalScheduleEvent,
)
from app.integrations.models import ImportType

logger = logging.getLogger(__name__)

CSV_ENTITY_TYPE_MAP = {
    ImportType.CUSTOMERS: CanonicalCustomer,
    ImportType.JOBS: CanonicalJob,
    ImportType.INVOICES: CanonicalInvoice,
    ImportType.EMPLOYEES: CanonicalEmployee,
    ImportType.ASSETS: CanonicalAsset,
    ImportType.SCHEDULE_EVENTS: CanonicalScheduleEvent,
}

DEFAULT_MAPPINGS = {
    ImportType.CUSTOMERS: {
        "name": "name",
        "email": "email",
        "phone": "phone",
        "address": "address_line1",
        "city": "city",
        "state": "state",
        "zip": "postal_code",
        "zip_code": "postal_code",
        "postal_code": "postal_code",
        "country": "country",
        "notes": "notes",
        "description": "notes",
    },
    ImportType.INVOICES: {
        "invoice_number": "invoice_number",
        "number": "invoice_number",
        "customer": "customer_external_id",
        "customer_id": "customer_external_id",
        "subtotal": "subtotal",
        "tax": "tax",
        "total": "total",
        "amount": "total",
        "status": "status",
        "due_date": "due_date",
        "date": "issued_date",
        "notes": "notes",
    },
    ImportType.JOBS: {
        "title": "title",
        "name": "title",
        "description": "description",
        "status": "status",
        "scheduled_start": "scheduled_start",
        "scheduled_end": "scheduled_end",
        "address": "address_line1",
        "city": "city",
        "state": "state",
        "zip": "postal_code",
        "customer": "customer_external_id",
        "customer_id": "customer_external_id",
        "assigned_to": "assigned_employee_external_id",
        "technician": "assigned_employee_external_id",
        "priority": "priority",
        "notes": "notes",
    },
    ImportType.EMPLOYEES: {
        "first_name": "first_name",
        "last_name": "last_name",
        "name": "first_name",
        "email": "email",
        "phone": "phone",
        "role": "role",
        "position": "role",
        "hire_date": "hire_date",
        "hourly_rate": "hourly_rate",
        "rate": "hourly_rate",
        "active": "is_active",
        "is_active": "is_active",
    },
    ImportType.ASSETS: {
        "name": "name",
        "asset_name": "name",
        "type": "asset_type",
        "asset_type": "asset_type",
        "serial": "serial_number",
        "serial_number": "serial_number",
        "status": "status",
        "assigned_to": "assigned_employee_external_id",
        "location": "location_external_id",
        "purchase_date": "purchase_date",
        "notes": "notes",
    },
    ImportType.SCHEDULE_EVENTS: {
        "title": "title",
        "name": "title",
        "description": "description",
        "start": "start_time",
        "start_time": "start_time",
        "end": "end_time",
        "end_time": "end_time",
        "employee_id": "employee_external_id",
        "assigned_to": "employee_external_id",
        "job_id": "job_external_id",
        "customer_id": "customer_external_id",
        "type": "event_type",
        "event_type": "event_type",
        "status": "status",
        "notes": "notes",
    },
}


class CSVImportEngine:
    def __init__(self, system_name: str = "csv"):
        self.system = system_name

    def preview(self, file_content: bytes, import_type: ImportType, delimiter: str = ",") -> dict:
        content = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        headers = reader.fieldnames or []
        rows = list(reader)[:10]

        return {
            "headers": headers,
            "sample_rows": rows,
            "total_rows_estimate": len(content.splitlines()) - 1,
            "import_type": import_type.value,
        }

    def parse(
        self,
        file_content: bytes,
        import_type: ImportType,
        column_mapping: dict[str, str] | None = None,
        delimiter: str = ",",
    ) -> list:
        content = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

        if reader.fieldnames is None:
            return []

        mapping = column_mapping if column_mapping else self._auto_map(reader.fieldnames, import_type)
        canonical_model = CSV_ENTITY_TYPE_MAP.get(import_type)
        if canonical_model is None:
            raise ValueError(f"Unsupported import type for CSV: {import_type}")

        records = []
        errors = []

        for row_num, row in enumerate(reader, start=2):
            mapped = self._apply_mapping(row, mapping)
            mapped["external_system"] = self.system
            mapped["external_id"] = f"csv_{import_type.value}_{hash(str(row))}"

            try:
                record = canonical_model(**mapped)
                records.append(record)
            except Exception as e:
                errors.append({"row": row_num, "error": str(e), "data": row})

        return records

    def _auto_map(self, headers: list[str], import_type: ImportType) -> dict[str, str]:
        defaults = DEFAULT_MAPPINGS.get(import_type, {})
        mapping = {}
        for header in headers:
            h_lower = header.lower().strip()
            if h_lower in defaults:
                mapping[header] = defaults[h_lower]
            else:
                mapping[header] = h_lower.replace(" ", "_").lower()
        return mapping

    def _apply_mapping(self, row: dict, mapping: dict[str, str]) -> dict:
        mapped = {}
        for source_col, dest_field in mapping.items():
            if source_col in row:
                val = row[source_col]
                if val is not None and str(val).strip():
                    mapped[dest_field] = str(val).strip()
        return mapped

    def generate_mapping_template(self, headers: list[str], import_type: ImportType) -> dict:
        defaults = DEFAULT_MAPPINGS.get(import_type, {})
        template = {}
        for header in headers:
            h_lower = header.lower().strip()
            template[header] = defaults.get(h_lower, "")
        return template
