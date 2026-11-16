import logging

from mcp_gateway.domain.external.model import ServiceRequest
from mcp_gateway.domain.exceptions import AppError
from mcp_gateway.domain.model.service import Service

from mcp_gateway.domain.model.service import (
    Service,
    ServiceEndpoint,
    ServiceAuthentication,
    ServiceDiscovery,
)

from mcp_gateway.domain.repository.server_repository import ServerRepository

from opentelemetry import trace

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

#---------------------------------
# Helper function to convert ServiceRequest to Service
#---------------------------------
def _to_service(payload: ServiceRequest) -> Service:
    return Service(
        server_id=payload.server_id,
        name=payload.name,
        description=payload.description,
        endpoint=ServiceEndpoint(
            url=payload.endpoint.url,
            transport=payload.endpoint.transport,
        ) if payload.endpoint else None,
        authentication=ServiceAuthentication(
            type=payload.authentication.type,
            audience=payload.authentication.audience,
        ) if payload.authentication else None,
        discovery=ServiceDiscovery(
            enabled=payload.discovery.enabled,
            refresh_interval_seconds=payload.discovery.refresh_interval_seconds,
        ) if payload.discovery else None,
        status=payload.status,
        created_at=payload.created_at,
        updated_at=payload.updated_at,
    )

class RegisteredServicesUseCase:
    def __init__(self, repo: ServerRepository):
        logger.info("Initializing RegisteredServicesUseCase")
        self.repo = repo
    
    async def get_registered_service(self, server_id: str) -> Service | None:
        with tracer.start_as_current_span("usecase.get_registered_service") as span:
            logger.info("Executing get_registered_service")

            response = None
            try:
                response = await self.repo.get_by_id(server_id)
            except AppError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error getting registered service: {e}")
                raise
                       
            return response
        
    async def add_registered_service(self, payload: ServiceRequest) -> Service:
        with tracer.start_as_current_span("usecase.add_registered_service") as span:
            logger.info("Executing add_registered_service")
            
            response = None
            try:
                response = await self.repo.create(_to_service(payload))
            except AppError as e:
                span.record_exception(e)
                raise
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Error adding registered service: {e}")
                raise
                       
            return response