from dataclasses import dataclass, field
from pydantic import Field
from mcp_gateway.domain.model.service import Service
from mcp_gateway.domain.model.a2a_agent import (
    A2AAgent,
    A2AAgentAuthentication,
    A2AAgentDiscovery,
    A2AAgentEndpoint,
)
from typing import Optional

# Result for the health check
@dataclass(frozen=True)
class HealthResponse:
    message: str
    
# Result for a single service
@dataclass(frozen=True)
class ServiceResponse:
    message: str
    service: Service

@dataclass(frozen=True)
class ServiceEndpointRequest:
    url: str
    transport: str

@dataclass(frozen=True)
class ServiceAuthenticationRequest:
    type: str
    audience: str

@dataclass(frozen=True)
class ServiceDiscoveryRequest:
    enabled: bool = Field(default=True)
    refresh_interval_seconds: int = Field(default=0)

@dataclass(frozen=True)
class ServiceRequest:
    server_id: str
    name: str
    description: str
    endpoint: Optional[ServiceEndpointRequest]
    authentication: Optional[ServiceAuthenticationRequest]
    discovery: Optional[ServiceDiscoveryRequest]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str] = None

@dataclass(frozen=True)
class A2AAgentResponse:
    message: str
    agent: A2AAgent

@dataclass(frozen=True)
class A2AAgentRequest:
    agent_id: str
    name: str
    description: str
    endpoint: Optional[A2AAgentEndpoint]
    authentication: Optional[A2AAgentAuthentication]
    discovery: Optional[A2AAgentDiscovery] = None
    owner: Optional[dict] = None
    url: Optional[str] = None
    version: Optional[str] = None
    provider: Optional[dict] = None
    supportedInterfaces: list[dict] = field(default_factory=list)
    capabilities: Optional[dict] = None
    securitySchemes: Optional[dict] = None
    security: list[dict] = field(default_factory=list)
    defaultInputModes: list[str] = field(default_factory=list)
    defaultOutputModes: list[str] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)
    status: str = "ACTIVE"
    discovered_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None