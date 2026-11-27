from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_gateway.domain.model.a2a_agent import A2AAgent

class A2AAgentRepository(ABC):
    @abstractmethod
    async def create(self, agent: A2AAgent) -> A2AAgent:
        raise NotImplementedError

    @abstractmethod
    async def get_document_by_id(self, agent_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    async def sync_capabilities(
        self,
        server_id: str,
        capabilities: list[dict],
        provider_type: str = "MCP",
    ) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def create_outbox_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        raise NotImplementedError
