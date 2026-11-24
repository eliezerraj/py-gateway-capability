from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import asyncpg

from mcp_gateway.domain.exceptions import AlreadyExistsError, RepositoryError
from mcp_gateway.domain.model.a2a_agent import A2AAgent
from mcp_gateway.domain.repository.a2a_agent_repository import A2AAgentRepository

from opentelemetry import trace

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


class PostgresA2AAgentRepository(A2AAgentRepository):
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create(self, agent: A2AAgent) -> A2AAgent:
        logger.info("Executing create registered a2a agent: %s", agent)
        with tracer.start_as_current_span("repository.create_registered_a2a_agent"):
            endpoint = self._resolve_endpoint(agent)
            document = self._a2a_agent_to_document(agent)
            document_json = json.dumps(document)
            now = datetime.now(timezone.utc)

            try:
                async with self._pool.acquire() as connection:
                    row = await connection.fetchrow(
                        """
                        INSERT INTO a2a_agent_registry (
                            agent_id,
                            endpoint,
                            status,
                            document,
                            discovered_at
                        )
                        VALUES ($1, $2, $3, $4::jsonb, $5)
                        RETURNING
                            agent_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        """,
                        agent.agent_id,
                        endpoint,
                        agent.status,
                        document_json,
                        now,
                    )
            except asyncpg.UniqueViolationError as exc:
                logger.warning("Unique violation error on create a2a agent: %s", exc)
                raise AlreadyExistsError(f"a2a agent '{agent.agent_id}' already exists") from exc
            except asyncpg.PostgresError as exc:
                logger.error(
                    "Postgres error on create a2a agent: %s | sqlstate=%s | detail=%s",
                    str(exc),
                    getattr(exc, "sqlstate", None),
                    getattr(exc, "detail", None),
                )
                raise RepositoryError("failed to create a2a_agent_registry record") from exc

            return self._to_domain(row)

    async def get_document_by_id(self, agent_id: str) -> dict | None:
        logger.info("Getting a2a agent card by id: %s", agent_id)
        with tracer.start_as_current_span("repository.get_a2a_agent_card_by_id"):
            try:
                async with self._pool.acquire() as connection:
                    row = await connection.fetchrow(
                        """
                        SELECT
                            agent_id,
                            endpoint,
                            status,
                            document,
                            discovered_at,
                            created_at,
                            updated_at
                        FROM a2a_agent_registry
                        WHERE agent_id = $1
                        """,
                        agent_id,
                    )
            except asyncpg.PostgresError as exc:
                logger.error(
                    "Postgres error on get a2a agent card: %s | sqlstate=%s | detail=%s",
                    str(exc),
                    getattr(exc, "sqlstate", None),
                    getattr(exc, "detail", None),
                )
                raise RepositoryError("failed to get a2a agent by id") from exc

            if row is None:
                return None

            return self._to_document(row)

    @staticmethod
    def _resolve_endpoint(agent: A2AAgent) -> str | None:
        if agent.endpoint:
            return agent.endpoint.url
        return None

    @staticmethod
    def _a2a_agent_to_document(agent: A2AAgent) -> dict:
        return agent.model_dump(mode="json", exclude_none=True)

    @staticmethod
    def _to_domain(row: asyncpg.Record) -> A2AAgent:
        document = PostgresA2AAgentRepository._to_document(row)
        return A2AAgent(**document)

    @staticmethod
    def _to_document(row: asyncpg.Record) -> dict:
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

        if "agent_id" not in document:
            document["agent_id"] = row["agent_id"]
        if "status" not in document:
            document["status"] = row["status"]
        if "endpoint" not in document and row["endpoint"] is not None:
            document["endpoint"] = {"url": row["endpoint"], "transport": "json-rpc"}
        if "discovered_at" not in document and discovered_at is not None:
            document["discovered_at"] = discovered_at.isoformat()
        if "created_at" not in document and created_at is not None:
            document["created_at"] = created_at.isoformat()
        if updated_at is not None:
            document["updated_at"] = updated_at.isoformat()

        return document
