import logging

from mcp_gateway.domain.external.model import A2AAgentRequest
from mcp_gateway.domain.exceptions import AppError
from mcp_gateway.domain.model.a2a_agent import A2AAgent
from mcp_gateway.domain.repository.a2a_agent_repository import A2AAgentRepository

from opentelemetry import trace

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


def _to_a2a_agent(payload: A2AAgentRequest) -> A2AAgent:
    return A2AAgent(
        agent_id=payload.agent_id,
        name=payload.name,
        description=payload.description,
        endpoint=payload.endpoint,
        authentication=payload.authentication,
        owner=payload.owner,
        discovery=payload.discovery,
        url=payload.url,
        version=payload.version,
        provider=payload.provider,
        supportedInterfaces=payload.supportedInterfaces,
        capabilities=payload.capabilities,
        securitySchemes=payload.securitySchemes,
        security=payload.security,
        defaultInputModes=payload.defaultInputModes,
        defaultOutputModes=payload.defaultOutputModes,
        skills=payload.skills,
        status=payload.status,
        discovered_at=payload.discovered_at,
        created_at=payload.created_at,
        updated_at=payload.updated_at,
    )


class A2ARegisteredAgentsUseCase:
    def __init__(self, repo: A2AAgentRepository):
        logger.info("Initializing A2ARegisteredAgentsUseCase")
        self.repo = repo

    async def add_registered_a2a_agent(self, payload: A2AAgentRequest) -> A2AAgent:
        with tracer.start_as_current_span("usecase.add_registered_a2a_agent") as span:
            logger.info("Executing add_registered_a2a_agent")

            response = None
            try:
                response = await self.repo.create(_to_a2a_agent(payload))
            except AppError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error adding registered a2a agent: {e}")
                raise

            return response
