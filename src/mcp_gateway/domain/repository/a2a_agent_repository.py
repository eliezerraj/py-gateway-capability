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
