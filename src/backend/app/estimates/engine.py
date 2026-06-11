import json
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ESTIMATE_SYSTEM_PROMPT = """You are WorkTicket's Job Estimation Engine for a skilled trades company.

Your job is to generate accurate job estimates using:
- company pricing rules
- service catalog
- labor rates
- fees
- markup rules
- historical job data (if available)

You must NEVER guess pricing. Only use provided company data.

Return a structured estimate with:
- line items
- labor calculation
- materials estimate (if applicable)
- fees
- total or range (based on company preference)

If information is missing, make conservative assumptions based on similar trade industry standards and clearly flag assumptions."""


def _build_estimate_prompt(
    job_description: str,
    customer_info: str | None,
    company_pricing: dict,
    historical_insights: str | None,
    service_catalog: list,
) -> str:
    parts = [f"Generate a job estimate.\n\nJOB DESCRIPTION:\n{job_description}"]
    if customer_info:
        parts.append(f"\nCUSTOMER:\n{customer_info}")
    parts.append(f"\n\nCOMPANY CONTEXT:\n{json.dumps(company_pricing, indent=2)}")
    if service_catalog:
        parts.append(f"\n\nSERVICE CATALOG:\n{json.dumps(service_catalog, indent=2)}")
    if historical_insights:
        parts.append(f"\n\nHISTORICAL INSIGHTS:\n{historical_insights}")

    parts.append("""
OUTPUT FORMAT:
Return ONLY valid JSON with this structure:
{
  "line_items": [
    {
      "name": "Service call fee",
      "item_type": "fee",
      "quantity": 1,
      "rate": 0,
      "total": 0
    },
    {
      "name": "Labor",
      "item_type": "labor",
      "quantity": 0,
      "rate": 0,
      "total": 0
    }
  ],
  "subtotal": 0,
  "tax": 0,
  "total": 0,
  "confidence_score": 75,
  "assumptions": ["Assumption 1"]
}

Rules:
- item_type must be one of: labor, materials, fee
- For labor items, quantity = hours, rate = hourly rate
- For fee items, quantity = 1, rate = fee amount
- subtotal = sum of all line item totals
- total = subtotal + tax
- confidence_score is 0-100
- assumptions is a list of strings noting any assumptions made""")
    return "\n".join(parts)


async def generate_estimate_ai(
    job_description: str,
    company_pricing: dict,
    customer_info: str | None = None,
    service_catalog: list | None = None,
    historical_insights: str | None = None,
) -> dict | None:
    from app.ai.gateway import _sanitize_output_dict, gateway

    prompt = _build_estimate_prompt(
        job_description=job_description,
        customer_info=customer_info,
        company_pricing=company_pricing,
        historical_insights=historical_insights,
        service_catalog=service_catalog or [],
    )

    result = await gateway.orchestrator.generate_chat_output(
        system_prompt=ESTIMATE_SYSTEM_PROMPT,
        user_prompt=prompt,
    )
    if result is None:
        return None
    return _sanitize_output_dict(result)  # type: ignore[no-any-return]


async def get_historical_insights(
    db: AsyncSession,
    company_id: UUID,
    service_type: str | None = None,
) -> str | None:
    from app.estimates.models import HistoricalJobData

    query = select(
        func.avg(HistoricalJobData.actual_hours).label("avg_hours"),
        func.avg(HistoricalJobData.actual_cost).label("avg_cost"),
        func.count(HistoricalJobData.id).label("job_count"),
        func.avg(HistoricalJobData.estimated_hours).label("avg_estimated_hours"),
    ).where(HistoricalJobData.company_id == company_id)

    if service_type:
        query = query.where(HistoricalJobData.service_type.ilike(f"%{service_type}%"))

    result = await db.execute(query)
    row = result.one_or_none()

    if not row or not row.job_count or row.job_count < 3:
        return None

    return (
        f"- Average time for similar jobs: {row.avg_hours:.1f} hours (estimated: {row.avg_estimated_hours:.1f})\n"
        f"- Average cost: ${row.avg_cost:.2f}\n"
        f"- Based on {row.job_count} completed jobs"
    )
