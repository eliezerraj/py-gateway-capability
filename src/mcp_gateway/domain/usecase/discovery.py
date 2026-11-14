import logging

from mcp_gateway.infrastructure.adapter.mcp import mcp_client
from mcp_gateway.domain.external.catalog import CatalogOutboxPayloadBuilder

from opentelemetry import trace
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
    mime_type_key: str = "mimeType",
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
    mime_type = payload.get(mime_type_key)

    return {
        "capability_type": capability_type,
        "name": name,
        "identifier": identifier,
        "description": description if isinstance(description, str) else None,
        "mime_type": mime_type if isinstance(mime_type, str) else None,
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


class DiscoveryServicesUseCase:
    
    def __init__(self, repo):
        logger.info("Initializing DiscoveryServicesUseCase")
        self.repo = repo
        
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
                await self.repo.sync_capabilities(server_id, capabilities)
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

            return {
                "service": service,
                "tools": tools,
                "resources": resources,
                "prompts": prompts,
                "resource_templates": resource_templates,
            }