from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from mcp_gateway.domain.repository.server_repository import ServerRepository
from mcp_gateway.infrastructure.database.postgres import (
    close_postgres_pool,
    create_postgres_pool,
)
from mcp_gateway.infrastructure.database.repository.postgres_repository import (
    PostgresServerRepository,
)

@dataclass
class Container:
    pool: asyncpg.Pool
    server_repository: ServerRepository

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
        server_repository=PostgresServerRepository(pool),
    )

async def shutdown_container(container: Container) -> None:
    await close_postgres_pool(container.pool)
