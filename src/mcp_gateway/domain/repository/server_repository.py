from __future__ import annotations

from abc import ABC, abstractmethod

from mcp_gateway.domain.model.service import Service

class ServerRepository(ABC):
    @abstractmethod
    async def create(self, service: Service) -> Service:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, server_id: str) -> Service | None:
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Service]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, service: Service) -> Service:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, server_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def sync_capabilities(self, server_id: str, capabilities: list[dict]) -> None:
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
