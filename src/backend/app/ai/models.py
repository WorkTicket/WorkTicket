# AIOutput model moved to app.jobs.models to avoid circular imports
# Re-export for backward compatibility
from app.jobs.models import AIOutput  # noqa: F401
