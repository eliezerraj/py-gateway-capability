from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

class A2AAgentEndpoint(BaseModel):
    url: str
    transport: str

class A2AAgentAuthentication(BaseModel):
    type: str
    audience: str

class A2AAgentDiscovery(BaseModel):
    enabled: bool = True
    refresh_interval_seconds: int = 0

class A2AAgent(BaseModel):
    agent_id: str
    name: str
    description: str
    endpoint: Optional[A2AAgentEndpoint] = None
    authentication: Optional[A2AAgentAuthentication] = None
    owner: Optional[dict] = None
    discovery: Optional[A2AAgentDiscovery] = None
    url: Optional[str] = None
    version: Optional[str] = None
    provider: Optional[dict] = None
    supportedInterfaces: list[dict] = Field(default_factory=list)
    capabilities: Optional[dict] = None
    securitySchemes: Optional[dict] = None
    security: list[dict] = Field(default_factory=list)
    defaultInputModes: list[str] = Field(default_factory=list)
    defaultOutputModes: list[str] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    status: str = "ACTIVE"
    discovered_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("updated_at", mode="before")
    @classmethod
    def normalize_updated_at(cls, value: Optional[str]) -> Optional[str]:
        if value == "":
            return None
        return value
