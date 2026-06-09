from uuid import UUID


class BaseMapper:
    """Maps canonical data into WorkTicket database models.

    Mappers take normalized canonical data and persist it into
    WorkTicket's native database tables. Each entity type has its
    own mapping method. Subclasses can override for provider-specific logic.
    """

    def __init__(self, db_session, company_id: UUID):
        self.db = db_session
        self.company_id = company_id

    async def map_customer(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_job(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_work_order(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_invoice(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_payment(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_employee(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_asset(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_location(self, canonical) -> str | None:
        raise NotImplementedError

    async def map_schedule_event(self, canonical) -> str | None:
        raise NotImplementedError
