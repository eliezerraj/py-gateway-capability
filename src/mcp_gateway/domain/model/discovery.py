from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

class DiscoveryServerInfo(BaseModel):
    name: str

class DiscoveryListChangedCapability(BaseModel):
    listChanged: bool = Field(default=True)

class DiscoveryResourcesCapability(BaseModel):
    listChanged: bool = Field(default=True)
    subscribe: bool = Field(default=True)

class DiscoveryCapabilities(BaseModel):
    tools: DiscoveryListChangedCapability
    prompts: DiscoveryListChangedCapability
    resources: DiscoveryResourcesCapability

class Discovery(BaseModel):
    serverId: str
    protocolVersion: str
    serverInfo: DiscoveryServerInfo
    capabilities: DiscoveryCapabilities
    tools: list[Any] = Field(default_factory=list)
    prompts: list[Any] = Field(default_factory=list)
    resources: list[Any] = Field(default_factory=list)
    resourceTemplates: list[Any] = Field(default_factory=list)
    discoveredAt: str

class DiscoveryResponse(BaseModel):
    message: str
    discovery: Discovery
    
class DiscoveryA2aResponse(BaseModel):
    message: str
    discovery: dict[str, Any] = Field(default_factory=dict)