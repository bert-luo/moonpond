"""Request models for the API layer."""

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    """Body for POST /api/generate."""

    prompt: str
