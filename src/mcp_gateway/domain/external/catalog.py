from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

@dataclass(frozen=True)
class CatalogSearchArguments:
    query: str
    capabilityTypes: list[str] = field(default_factory=list)
    serverIds: list[str] = field(default_factory=list)
    limit: int = 5

@dataclass(frozen=True)
class CatalogSearchRequest:
    arguments: CatalogSearchArguments
    name: str = "catalog_search"

@dataclass(frozen=True)
class CatalogSearchResult:
    capabilityId: str
    serverId: str
    capabilityType: str
    name: str
    description: str
    score: float

@dataclass(frozen=True)
class CatalogSearchResponse:
    message: str
    results: list[CatalogSearchResult] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogDocumentSource:
    server_id: str
    capability_type: str
    name: str
    identifier: str
    description: str
    search_text: str
    input_fields: list[str] = field(default_factory=list)
    input_tokens: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    template_variables: list[str] = field(default_factory=list)
    operation: str = "read"
    domain: str = "generic"
    side_effect: bool = False
    enabled: bool = True
    source_updated_at: str = ""


@dataclass(frozen=True)
class CatalogDocument:
    documentId: str
    operation: str
    source: CatalogDocumentSource


@dataclass(frozen=True)
class CatalogStatistics:
    tools: int = 0
    prompts: int = 0
    resources: int = 0
    resource_templates: int = 0
    total: int = 0


@dataclass(frozen=True)
class CatalogOutboxPayload:
    schemaVersion: int
    eventType: str
    operation: str
    index: str
    serverId: str
    catalogGeneration: int
    discoveredAt: str
    documents: list[CatalogDocument] = field(default_factory=list)
    statistics: CatalogStatistics = field(default_factory=CatalogStatistics)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CatalogOutboxPayloadBuilder:
    _RESOURCE_TEMPLATE_VAR_PATTERN = re.compile(r"\{([^}]+)\}")
    _DOMAIN_TOKENS = ("inventory", "order", "payment", "authorizer")

    @classmethod
    def build(
        cls,
        *,
        server_id: str,
        capabilities: list[dict[str, Any]],
        discovered_at: str | None = None,
        catalog_generation: int = 1,
        index_name: str = "mcp-capabilities-v1",
    ) -> dict[str, Any]:
        discovered_timestamp = discovered_at or datetime.now(timezone.utc).isoformat()

        documents = [cls._to_document(server_id, capability, discovered_timestamp) for capability in capabilities]
        statistics = cls._build_statistics(capabilities)

        payload = CatalogOutboxPayload(
            schemaVersion=1,
            eventType="MCP_SEARCH_CATALOG_REPLACE",
            operation="REPLACE_SERVER_CATALOG",
            index=index_name,
            serverId=server_id,
            catalogGeneration=catalog_generation,
            discoveredAt=discovered_timestamp,
            documents=documents,
            statistics=statistics,
        )

        return payload.to_dict()

    @classmethod
    def build_source(
        cls,
        server_id: str,
        capability: dict[str, Any],
        discovered_at: str,
    ) -> CatalogDocumentSource:
        return cls._to_document(server_id, capability, discovered_at).source

    @classmethod
    def _to_document(
        cls,
        server_id: str,
        capability: dict[str, Any],
        discovered_at: str,
    ) -> CatalogDocument:
        capability_type = str(capability.get("capability_type", "")).strip()
        name = str(capability.get("name", "")).strip()
        identifier = str(capability.get("identifier", "")).strip()
        description_raw = capability.get("description")
        description = cls._normalize_space(description_raw) if isinstance(description_raw, str) else ""
        payload = capability.get("payload")
        payload_obj = payload if isinstance(payload, dict) else {}

        input_fields, required_fields = cls._extract_input_fields(payload_obj)
        input_tokens = cls._build_input_tokens(input_fields)
        template_variables = cls._extract_template_variables(capability_type, identifier)
        operation = cls._resolve_operation(capability_type, name)
        domain = cls._resolve_domain(server_id)
        side_effect = cls._resolve_side_effect(capability_type, operation)
        search_text = cls._build_search_text(description, operation, input_fields, template_variables)

        source = CatalogDocumentSource(
            server_id=server_id,
            capability_type=capability_type,
            name=name,
            identifier=identifier,
            description=description,
            search_text=search_text,
            input_fields=input_fields,
            input_tokens=input_tokens,
            required_fields=required_fields,
            template_variables=template_variables,
            operation=operation,
            domain=domain,
            side_effect=side_effect,
            enabled=True,
            source_updated_at=discovered_at,
        )

        document_id = cls._hash_text(f"{server_id}:{capability_type}:{identifier}")

        return CatalogDocument(
            documentId=document_id,
            operation="INDEX",
            source=source,
        )

    @classmethod
    def _extract_input_fields(cls, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
        schema = payload.get("inputSchema")
        if not isinstance(schema, dict):
            return [], []

        fields: list[str] = []
        required_fields: list[str] = []

        visited: set[str] = set()

        def walk(node: dict[str, Any]) -> None:
            node_id = str(id(node))
            if node_id in visited:
                return
            visited.add(node_id)

            properties = node.get("properties")
            if isinstance(properties, dict):
                for key, value in properties.items():
                    if key not in fields:
                        fields.append(key)
                    if isinstance(value, dict):
                        walk(value)

            required = node.get("required")
            if isinstance(required, list):
                for item in required:
                    if isinstance(item, str) and item not in required_fields:
                        required_fields.append(item)

            defs = node.get("$defs")
            if isinstance(defs, dict):
                for sub_schema in defs.values():
                    if isinstance(sub_schema, dict):
                        walk(sub_schema)

            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                ref_name = ref.split("/")[-1]
                defs = schema.get("$defs")
                if isinstance(defs, dict):
                    target = defs.get(ref_name)
                    if isinstance(target, dict):
                        walk(target)

            any_of = node.get("anyOf")
            if isinstance(any_of, list):
                for sub_schema in any_of:
                    if isinstance(sub_schema, dict):
                        walk(sub_schema)

        walk(schema)
        return fields, required_fields

    @classmethod
    def _extract_template_variables(cls, capability_type: str, identifier: str) -> list[str]:
        if capability_type != "resource_template":
            return []
        return [match.strip() for match in cls._RESOURCE_TEMPLATE_VAR_PATTERN.findall(identifier) if match.strip()]

    @classmethod
    def _build_input_tokens(cls, input_fields: list[str]) -> list[str]:
        tokens: list[str] = []
        for field_name in input_fields:
            normalized = cls._normalize_space(re.sub(r"[._]+", " ", field_name)).lower()
            if normalized and normalized not in tokens:
                tokens.append(normalized)
        return tokens

    @staticmethod
    def _resolve_operation(capability_type: str, name: str) -> str:
        if capability_type in {"resource", "resource_template"}:
            return "read"
        if capability_type == "prompt":
            return "workflow"

        lowered = name.lower()
        if lowered.startswith(("post_", "create_", "add_")):
            return "create"
        if lowered.startswith(("put_", "patch_", "update_")):
            return "update"
        if lowered.startswith(("delete_", "remove_")):
            return "delete"
        if lowered.startswith(("get_", "list_", "search_", "read_")):
            return "read"
        return "execute"

    @classmethod
    def _resolve_domain(cls, server_id: str) -> str:
        lowered = server_id.lower()
        for token in cls._DOMAIN_TOKENS:
            if token in lowered:
                return token
        return "generic"

    @staticmethod
    def _resolve_side_effect(capability_type: str, operation: str) -> bool:
        if capability_type in {"resource", "resource_template", "prompt"}:
            return False
        return operation in {"create", "update", "delete", "execute"}

    @staticmethod
    def _build_search_text(
        description: str,
        operation: str,
        input_fields: list[str],
        template_variables: list[str],
    ) -> str:
        parts: list[str] = []
        if description:
            parts.append(description)
        if input_fields:
            parts.append("Input fields: " + ", ".join(input_fields))
        if template_variables:
            parts.append("Template variables: " + ", ".join(template_variables))
        parts.append(f"Operation: {operation}")
        return ". ".join(part for part in parts if part)

    @staticmethod
    def _build_statistics(capabilities: list[dict[str, Any]]) -> CatalogStatistics:
        counts = {
            "tool": 0,
            "prompt": 0,
            "resource": 0,
            "resource_template": 0,
        }
        for capability in capabilities:
            capability_type = capability.get("capability_type")
            if capability_type in counts:
                counts[capability_type] += 1

        return CatalogStatistics(
            tools=counts["tool"],
            prompts=counts["prompt"],
            resources=counts["resource"],
            resource_templates=counts["resource_template"],
            total=sum(counts.values()),
        )

    @staticmethod
    def _normalize_space(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_json(value: dict[str, Any]) -> str:
        canonical_json = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()