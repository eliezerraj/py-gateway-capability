import logging

from mcp_gateway.infrastructure.adapter.mcp import mcp_client
from mcp_gateway.domain.external.catalog import CatalogOutboxPayloadBuilder
from mcp_gateway.domain.repository.a2a_agent_repository import A2AAgentRepository
from mcp_gateway.domain.repository.mcp_server_repository import ServerRepository
from mcp_gateway.infrastructure.adapter.http.http_client import HttpAdapter

from opentelemetry import trace

from mcp_gateway.domain.model.discovery import (
    DiscoveryA2aResponse,
    Discovery,
    DiscoveryCapabilities,
    DiscoveryListChangedCapability,
    DiscoveryResourcesCapability,
    DiscoveryResponse,
    DiscoveryServerInfo,
)

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

def _normalize_capability(
    capability_type: str,
    payload: dict,
    *,
    name_key: str = "name",
    identifier_key: str | None = None,
    fallback_identifier_key: str | None = None,
) -> dict:
    name = payload.get(name_key)
    identifier = payload.get(identifier_key) if identifier_key else None
    if identifier is None and fallback_identifier_key:
        identifier = payload.get(fallback_identifier_key)
    if identifier is None:
        identifier = name

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Invalid {capability_type} capability: missing name")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError(f"Invalid {capability_type} capability: missing identifier")

    description = payload.get("description")
    return {
        "capability_type": capability_type,
        "name": name,
        "identifier": identifier,
        "description": description if isinstance(description, str) else None,
        "payload": payload,
    }

def _build_capability_records(
    tools: list[dict],
    prompts: list[dict],
    resources: list[dict],
    resource_templates: list[dict],
) -> list[dict]:
    capabilities: list[dict] = []

    for tool in tools:
        capabilities.append(_normalize_capability("tool", tool))

    for prompt in prompts:
        capabilities.append(_normalize_capability("prompt", prompt))

    for resource in resources:
        capabilities.append(
            _normalize_capability(
                "resource",
                resource,
                identifier_key="uri",
            )
        )

    for resource_template in resource_templates:
        capabilities.append(
            _normalize_capability(
                "resource_template",
                resource_template,
                identifier_key="uriTemplate",
                fallback_identifier_key="uri",
            )
        )

    return capabilities


def _build_a2a_skill_capability_records(agent_card: dict) -> list[dict]:
    capabilities: list[dict] = []
    skills = agent_card.get("skills")
    if not isinstance(skills, list):
        return capabilities

    for skill in skills:
        if not isinstance(skill, dict):
            continue

        identifier = skill.get("id")
        name = skill.get("name")

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(identifier, str) or not identifier.strip():
            identifier = name

        description = skill.get("description")
        capabilities.append(
            {
                "capability_type": "skill",
                "name": name,
                "identifier": identifier,
                "description": description if isinstance(description, str) else None,
                "payload": skill,
            }
        )

    return capabilities

class DiscoveryServicesUseCase:
    
    def __init__(
        self,
        repo: ServerRepository,
        a2a_repo: A2AAgentRepository,
    ):
        logger.info("Initializing DiscoveryServicesUseCase")
        self.repo = repo
        self.a2a_repo = a2a_repo
        self.http_adapter = HttpAdapter()
        
    async def get_discovery_service(self, server_id: str) -> dict | None:
        logger.info("Executing get_discovery_service with server_id=%s", server_id)
        
        with tracer.start_as_current_span("usecase.get_registered_service") as span:
            
            try:
                service = await self.repo.get_by_id(server_id)
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error getting registered service: {e}")
                raise

            if service is None:
                return None

            if service.endpoint is None or not service.endpoint.url:
                logger.warning("Service %s does not have endpoint URL configured", server_id)
                return {
                    "service": service,
                    "tools": [],
                    "resources": [],
                    "prompts": [],
                    "resource_templates": [],
                }

            try:
                tools = await mcp_client.mcp_tools_discovery(service.endpoint.url)
                resources = await mcp_client.mcp_resources_discovery(service.endpoint.url)
                prompts = await mcp_client.mcp_prompts_discovery(service.endpoint.url)
                resource_templates = await mcp_client.mcp_resource_templates_discovery(service.endpoint.url)

                capabilities = _build_capability_records(
                    tools=tools,
                    prompts=prompts,
                    resources=resources,
                    resource_templates=resource_templates,
                )
                await self.repo.sync_capabilities(
                    server_id,
                    capabilities,
                    provider_type="MCP",
                )
                
                payload_opensearch = CatalogOutboxPayloadBuilder.build(
                    server_id=server_id,
                    capabilities=capabilities,
                )
                
                await self.repo.create_outbox_event(
                    aggregate_type="mcp_server",
                    aggregate_id=server_id,
                    event_type="capabilities_discovered",
                    payload=payload_opensearch,
                )
                
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error processing discovery service response: {e}")
                raise

            discovery = {
                "serverId": service.server_id,
                "protocolVersion": "2025-06-18",
                "serverInfo": DiscoveryServerInfo(
                    name=service.name,
                ),
                "capabilities": DiscoveryCapabilities(
                    tools=DiscoveryListChangedCapability(listChanged=True),
                    prompts=DiscoveryListChangedCapability(listChanged=True),
                    resources=DiscoveryResourcesCapability(
                        listChanged=True,
                        subscribe=True,
                    ),
                ),
                "tools": tools,
                "prompts": prompts,
                "resources": resources,
                "resourceTemplates": resource_templates,
                "discoveredAt": service.created_at or "",
            }
                        
            return discovery

    async def post_discovery_a2a_service(self, agent_id: str) -> DiscoveryA2aResponse | None:
        logger.info("Executing post_discovery_a2a_service with agent_id=%s", agent_id)
        
        with tracer.start_as_current_span("usecase.post_discovery_a2a_service") as span:
            try:
                service = await self.a2a_repo.get_document_by_id(agent_id)
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error getting registered a2a agent: {e}")
                raise
            
            if service is None:
                return None

            endpoint = service.get("endpoint")
            endpoint_url = endpoint.get("url") if isinstance(endpoint, dict) else None
            if not isinstance(endpoint_url, str) or not endpoint_url:
                logger.warning("Service %s does not have endpoint URL configured", agent_id)
                return {
                    "service": service,
                    "skills": [],
                }
            
            agent_card = service
            try:
                a2a_response = await self.http_adapter.get(
                    base_url=endpoint_url,
                    path="/.well-known/agent-card.json",
                )
                if isinstance(a2a_response, dict):
                    agent_card = a2a_response
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error processing a2a service skills: {e}")
                raise

            capabilities = _build_a2a_skill_capability_records(agent_card)

            try:
                await self.repo.sync_capabilities(
                    agent_id,
                    capabilities,
                    provider_type="A2A",
                )

                payload_opensearch = CatalogOutboxPayloadBuilder.build(
                    server_id=agent_id,
                    capabilities=capabilities,
                )

                await self.repo.create_outbox_event(
                    aggregate_type="a2a_agent",
                    aggregate_id=agent_id,
                    event_type="capabilities_discovered",
                    payload=payload_opensearch,
                )
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error processing a2a discovery response: {e}")
                raise

            name = service.get("name")
            if not isinstance(name, str) or not name.strip():
                name = agent_id
            discovered_at = service.get("created_at")
            if not isinstance(discovered_at, str):
                discovered_at = ""

            discovery = {
                "serverId": agent_id,
                "protocolVersion": "2025-06-18",
                "serverInfo": DiscoveryServerInfo(
                    name=name,
                ),
                "skills": capabilities,
                "discoveredAt": discovered_at,
            }

            return DiscoveryA2aResponse(
                message=f"A2A agent {agent_id} discovery retrieved successfully",
                discovery=discovery,
            )