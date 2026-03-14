"""Response models for the API layer."""

from pydantic import BaseModel


class GenerateResponse(BaseModel):
    """Response from POST /api/generate."""

    job_id: str
