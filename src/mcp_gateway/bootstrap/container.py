from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from mcp_gateway.domain.repository.a2a_agent_repository import A2AAgentRepository
from mcp_gateway.domain.repository.mcp_server_repository import MCPServerRepository
from mcp_gateway.infrastructure.database.postgres import (
    close_postgres_pool,
    create_postgres_pool,
)
from mcp_gateway.infrastructure.database.repository.postgres_a2a_agent_repository import (
    PostgresA2AAgentRepository,
)
from mcp_gateway.infrastructure.database.repository.postgres_mcp_server_repository import (
    PostgresMCPServerRepository,
)

@dataclass
class Container:
    pool: asyncpg.Pool
    mcp_server_repository: MCPServerRepository
    a2a_agent_repository: A2AAgentRepository

async def create_container(
    dsn: str,
    *,
    min_pool_size: int = 1,
    max_pool_size: int = 10,
) -> Container:
    pool = await create_postgres_pool(
        dsn,
        min_size=min_pool_size,
        max_size=max_pool_size,
    )
    return Container(
        pool=pool,
        mcp_server_repository=PostgresMCPServerRepository(pool),
        a2a_agent_repository=PostgresA2AAgentRepository(pool),
    )

async def shutdown_container(container: Container) -> None:
    await close_postgres_pool(container.pool)
