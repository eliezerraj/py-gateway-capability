from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

class ServiceEndpoint(BaseModel):
    url: str
    transport: str

class ServiceAuthentication(BaseModel):
    type: str
    audience: str
    
class ServiceDiscovery(BaseModel):
    enabled: bool = Field(default=True)
    refresh_interval_seconds: int = Field(default=0)
    
class Service(BaseModel):
    server_id: str
    name: str
    description: str
    endpoint: Optional[ServiceEndpoint]
    authentication: Optional[ServiceAuthentication]
    discovery: Optional[ServiceDiscovery]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str] = None

    @field_validator("updated_at", mode="before")
    @classmethod
    def normalize_updated_at(cls, value: Optional[str]) -> Optional[str]:
        if value == "":
            return None
        return value