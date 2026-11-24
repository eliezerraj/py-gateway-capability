from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
import json
import asyncpg

from datetime import timezone

from mcp_gateway.domain.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    RepositoryError,
)
from mcp_gateway.domain.model.service import Service
from mcp_gateway.domain.repository.mcp_server_repository import ServerRepository

from opentelemetry import trace
#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

class PostgresServerRepository(ServerRepository):
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, service: Service) -> Service:
        logger.info(f"Executing create registered service: {service}")
        with tracer.start_as_current_span("usecase.create_registered_service") as span:
            
            server_id = self._resolve_server_id(service)
            endpoint = self._resolve_endpoint(service)
            status_value = service.status.value if hasattr(service.status, "value") else service.status
            document = self._service_to_document(service)
            document_json = json.dumps(document)
            now = datetime.now(timezone.utc)

            try:
                async with self._pool.acquire() as connection:
                    row = await connection.fetchrow(
                        """
                        INSERT INTO mcp_server_registry (
                            server_id,
                            endpoint,
                            status,
                            document,
                            discovered_at
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING
                            server_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        """,
                        server_id,
                        endpoint,
                        status_value,
                        document_json,
                        now,
                    )
            except asyncpg.UniqueViolationError as exc:
                logger.warning(f"Unique violation error on create: {exc}")
                raise AlreadyExistsError(f"mcp server '{server_id}' already exists") from exc
            except asyncpg.PostgresError as exc:
                logger.error(
                    "Postgres error on create: %s | sqlstate=%s | detail=%s",
                    str(exc),
                    getattr(exc, "sqlstate", None),
                    getattr(exc, "detail", None),
                )
                raise RepositoryError(f"failed to createmcp_server_registry {str(exc)}") from exc

            return self._to_domain(row)

    async def get_by_id(self, server_id: str) -> Service | None:
        logger.info(f"Getting mcp server by id: {server_id}")
        with tracer.start_as_current_span("usecase.get_mcp_server_by_id") as span:
            try:
                async with self._pool.acquire() as connection:
                    row = await connection.fetchrow(
                        """
                        SELECT
                            server_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        FROM mcp_server_registry
                        WHERE server_id = $1
                        """,
                        server_id,
                    )
            except asyncpg.PostgresError as exc:
                logger.error(
                    "Postgres error on get_by_id: %s | sqlstate=%s | detail=%s",
                    str(exc),
                    getattr(exc, "sqlstate", None),
                    getattr(exc, "detail", None),
                )
                raise RepositoryError("failed to get mcp server by id") from exc

            if row is None:
                logger.warning("No mcp server found with id: %s", server_id)
                return None

            return self._to_domain(row)

    async def list( self, status: str | None = None, limit: int = 100, offset: int = 0, ) -> list[Service]: 
        effective_limit = min(limit, 100)

        try:
            async with self._pool.acquire() as connection:
                if status is None:
                    rows = await connection.fetch(
                        """
                        SELECT
                            server_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        FROM mcp_server_registry
                        ORDER BY created_at DESC
                        LIMIT $1
                        OFFSET $2
                        """,
                        effective_limit,
                        offset,
                    )
                else:
                    rows = await connection.fetch(
                        """
                        SELECT
                            server_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        FROM mcp_server_registry
                        WHERE status = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                        OFFSET $3
                        """,
                        status,
                        effective_limit,
                        offset,
                    )
        except asyncpg.PostgresError as exc:
            raise RepositoryError("failed to list mcp servers") from exc

        return [self._to_domain(row) for row in rows]

    async def update(self, service: Service) -> Service:
        server_id = self._resolve_server_id(service)
        endpoint = self._resolve_endpoint(service)
        status_value = service.status.value if hasattr(service.status, "value") else service.status
        document = self._service_to_document(service)
        document_json = json.dumps(document)
        try:
            async with self._pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    UPDATE mcp_server_registry
                    SET
                        endpoint = $2,
                        status = $3,
                        document = $4::jsonb,
                        discovered_at = NOW(),
                        created_at = NOW()
                    WHERE server_id = $1
                    RETURNING
                        server_id,
                        endpoint,
                        status,
                        document,
                        discovered_at,
                        created_at,
                        updated_at
                    """,
                    server_id,
                    endpoint,
                    status_value,
                    document_json,
                    None,
                )
        except asyncpg.PostgresError as exc:
            raise RepositoryError("failed to update mcp server") from exc

        if row is None:
            raise NotFoundError(f"mcp server '{server_id}' not found")

        return self._to_domain(row)

    async def sync_capabilities(
        self,
        server_id: str,
        capabilities: list[dict],
        provider_type: str = "MCP",
    ) -> None:
        logger.info(
            "Syncing capabilities for provider_type=%s, provider_id=%s",
            provider_type,
            server_id,
        )
        
        with tracer.start_as_current_span("usecase.sync_capabilities") as span:
            capability_rows: list[tuple[str, str, str, str | None, str]] = []
            identifiers_by_type: dict[str, list[str]] = {}

            for capability in capabilities:
                capability_type = capability.get("capability_type")
                name = capability.get("name")
                identifier = capability.get("identifier")
                payload = capability.get("payload")

                if not capability_type or not isinstance(capability_type, str):
                    raise RepositoryError("capability_type is required for capability sync")
                if not name or not isinstance(name, str):
                    raise RepositoryError("name is required for capability sync")
                if not identifier or not isinstance(identifier, str):
                    raise RepositoryError("identifier is required for capability sync")
                if not isinstance(payload, dict):
                    raise RepositoryError("payload must be an object for capability sync")

                description = capability.get("description")
                payload_json = json.dumps(payload)

                capability_rows.append(
                    (
                        capability_type,
                        name,
                        identifier,
                        description,
                        payload_json,
                    )
                )
                identifiers_by_type.setdefault(capability_type, []).append(identifier)

            try:
                async with self._pool.acquire() as connection:
                    async with connection.transaction():
                        for row in capability_rows:
                            capability_type, name, identifier, description, payload_json = row
                            await connection.execute(
                                """
                                INSERT INTO capability_catalog (
                                    provider_type,
                                    provider_id,
                                    capability_type,
                                    name,
                                    identifier,
                                    description,
                                    payload,
                                    enabled,
                                    discovered_at
                                )
                                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, TRUE, NOW())
                                ON CONFLICT (provider_type, provider_id, capability_type, identifier)
                                DO UPDATE SET
                                    name = EXCLUDED.name,
                                    description = EXCLUDED.description,
                                    payload = EXCLUDED.payload,
                                    enabled = TRUE,
                                    discovered_at = NOW(),
                                    updated_at = NOW()
                                """,
                                provider_type,
                                server_id,
                                capability_type,
                                name,
                                identifier,
                                description,
                                payload_json,
                            )

                        for capability_type, identifiers in identifiers_by_type.items():
                            if identifiers:
                                await connection.execute(
                                    """
                                    UPDATE capability_catalog
                                    SET
                                        enabled = FALSE,
                                        updated_at = NOW()
                                    WHERE provider_type = $1
                                    AND provider_id = $2
                                    AND capability_type = $3
                                    AND identifier <> ALL($4::text[])
                                    """,
                                    provider_type,
                                    server_id,
                                    capability_type,
                                    identifiers,
                                )
                            else:
                                await connection.execute(
                                    """
                                    UPDATE capability_catalog
                                    SET
                                        enabled = FALSE,
                                        updated_at = NOW()
                                    WHERE provider_type = $1
                                    AND provider_id = $2
                                    AND capability_type = $3
                                    """,
                                    provider_type,
                                    server_id,
                                    capability_type,
                                )
            except asyncpg.PostgresError as exc:
                logger.error(
                    "Postgres error on get_by_id: %s | sqlstate=%s | detail=%s",
                    str(exc),
                    getattr(exc, "sqlstate", None),
                    getattr(exc, "detail", None),
                )
                raise RepositoryError("failed to sync mcp capabilities") from exc

    async def create_outbox_event(self, *, aggregate_type: str, aggregate_id: str, event_type: str, payload: dict) -> None:
        logger.info("Creating outbox event for aggregate_type=%s, aggregate_id=%s, event_type=%s", aggregate_type, aggregate_id, event_type)
        
        if not aggregate_type:
            raise RepositoryError("aggregate_type is required for outbox event")
        if not aggregate_id:
            raise RepositoryError("aggregate_id is required for outbox event")
        if not event_type:
            raise RepositoryError("event_type is required for outbox event")
        if not isinstance(payload, dict):
            raise RepositoryError("payload must be an object for outbox event")

        payload_json = json.dumps(payload)

        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        """
                        INSERT INTO public.outbox_event (
                            aggregate_type,
                            aggregate_id,
                            event_type,
                            payload
                        )
                        VALUES ($1, $2, $3, $4::jsonb)
                        """,
                        aggregate_type,
                        aggregate_id,
                        event_type,
                        payload_json,
                    )
        except asyncpg.PostgresError as exc:
            logger.error(
                "Postgres error on create_outbox_event: %s | sqlstate=%s | detail=%s",
                str(exc),
                getattr(exc, "sqlstate", None),
                getattr(exc, "detail", None),
            )
            raise RepositoryError("failed to create outbox event") from exc

    @staticmethod
    def _resolve_server_id(service: Service) -> str:
        if service.server_id:
            return service.server_id
        raise RepositoryError("service.server_id is required")

    @staticmethod
    def _resolve_endpoint(service: Service) -> str:
        if service.endpoint:
            return service.endpoint.url

        raise RepositoryError("service.endpoint is required")

    @staticmethod
    def _service_to_document(service: Service) -> dict:
        return service.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _to_domain(row: asyncpg.Record) -> Service:
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        discovered_at = row["discovered_at"]

        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if discovered_at is not None and discovered_at.tzinfo is None:
            discovered_at = discovered_at.replace(tzinfo=timezone.utc)

        raw_document = row["document"]
        if isinstance(raw_document, str):
            document = json.loads(raw_document)
        elif isinstance(raw_document, dict):
            document = raw_document
        else:
            document = {}

        document.pop("created_at", None)
        document.pop("updated_at", None)

        if "server_id" not in document:
            document["server_id"] = row["server_id"]
        if "status" not in document:
            document["status"] = row["status"]
        if "created_at" not in document and created_at is not None:
            document["created_at"] = created_at.isoformat()
        if updated_at is not None:
            document["updated_at"] = updated_at.isoformat()
        if "endpoint" not in document:
            document["endpoint"] = {"url": row["endpoint"], "transport": "streamable-http"}

        return Service(**document)
