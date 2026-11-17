import logging

from fastapi import APIRouter, status, Request

from mcp_gateway.domain.external.model import (
    A2AAgentRequest,
    A2AAgentResponse,
    HealthResponse,
    ServiceRequest,
    ServiceResponse,
)
from mcp_gateway.domain.external.catalog import (
    CatalogSearchRequest,
    CatalogSearchResult,
    CatalogSearchResponse,
)
from mcp_gateway.domain.model.discovery import (
    Discovery,
    DiscoveryCapabilities,
    DiscoveryListChangedCapability,
    DiscoveryResourcesCapability,
    DiscoveryResponse,
    DiscoveryServerInfo,
    DiscoveryA2aResponse,
)

from mcp_gateway.domain.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    RepositoryError,
    ServiceError,
)

from mcp_gateway.domain.usecase.health import HealthUseCase
from mcp_gateway.domain.usecase.discovery import DiscoveryServicesUseCase
from mcp_gateway.domain.usecase.a2a_register import A2ARegisteredAgentsUseCase
from mcp_gateway.domain.usecase.mcp_register import RegisteredServicesUseCase

from mcp_gateway.domain.external.error_response import AppError

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Health"],
)

#----------------------------------------------
# Registered health endpoint for the gateway
@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Check gateway health",
)

#----------------------------------------------
# Health check endpoint for the gateway
def get_health() -> HealthResponse:
    use_case = HealthUseCase()
    result = use_case.execute()

    return HealthResponse(message=result.message)

#----------------------------------------------
# Registered services endpoint for the gateway
@router.post(
    "/v1/mcp/service",
    response_model=ServiceResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Post registered services",
)
async def get_registered_services(payload: ServiceRequest, request: Request) -> ServiceResponse:
    logger.info("Executing get_registered_services endpoint : payload=%s", payload)
    with tracer.start_as_current_span("router.get_registered_service") as span:
        try:
            repo = request.app.state.container.server_repository
            use_case = RegisteredServicesUseCase(repo)

            result = await use_case.add_registered_service(payload)
            message = f"Service {result.name} added successfully"

            return ServiceResponse(message=message, service=result)
        
        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error adding registered service: {e}")
            raise ServiceError(message=f"Error adding registered service: {e}") from e

#----------------------------------------------
# Registered a2a agent endpoint for the gateway
@router.post(
    "/v1/a2a/service",
    response_model=A2AAgentResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Post registered a2a agent",
)
async def get_registered_a2a_agent(payload: A2AAgentRequest, request: Request) -> A2AAgentResponse:
    logger.info("Executing get_registered_a2a_agent endpoint : payload=%s", payload)
    with tracer.start_as_current_span("router.get_registered_a2a_agent") as span:
        try:
            repo = request.app.state.container.a2a_agent_repository
            use_case = A2ARegisteredAgentsUseCase(repo)

            result = await use_case.add_registered_a2a_agent(payload)
            message = f"A2A agent {result.agent_id} added successfully"

            return A2AAgentResponse(message=message, agent=result)

        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error adding registered a2a agent: {e}")
            raise ServiceError(message=f"Error adding registered a2a agent: {e}") from e

#----------------------------------------------
# Get registered services endpoint for the gateway
@router.get(
    "/v1/mcp/service/{server_id}",
    response_model=ServiceResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Get registered service by server id",
)
async def get_registered_service(server_id: str, request: Request) -> ServiceResponse:
    logger.info("Executing get_registered_service endpoint : server_id=%s", server_id)
    with tracer.start_as_current_span("router.get_registered_service") as span:
        try:
            repo = request.app.state.container.server_repository
            use_case = RegisteredServicesUseCase(repo)

            result = await use_case.get_registered_service(server_id)
            
            if result is None:
                raise NotFoundError(message=f"Service {server_id} not found")
            
            message = f"Service {result.name} retrieved successfully"
            return ServiceResponse(message=message, service=result)
        
        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error retrieving registered service: {e}")
            raise ServiceError(message=f"Error retrieving registered service: {e}") from e

#----------------------------------------------
# Discovery
@router.post(
    "/v1/mcp/discovery/{server_id}",
    response_model=DiscoveryResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Post discovery information for service by server id",
)
async def get_discovery_info(server_id: str, request: Request) -> DiscoveryResponse:
    logger.info("Executing get_discovery_info endpoint : server_id=%s", server_id)
    with tracer.start_as_current_span("router.get_discovery_info") as span:
        try:
            repo = request.app.state.container.server_repository
            a2a_repo = request.app.state.container.a2a_agent_repository
            use_case = DiscoveryServicesUseCase(repo, a2a_repo)

            result = await use_case.get_discovery_service(server_id)
            if result is None:
                raise NotFoundError(message=f"Service {server_id} not found")
            
            message = f"Service {server_id} discovery retrieved successfully"

            return DiscoveryResponse(
                message=message,
                discovery=result
            )
            
        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error retrieving registered service: {e}")
            raise ServiceError(message=f"Error retrieving registered service: {e}") from e

#----------------------------------------------
# Discovery A2A
@router.post(
    "/v1/a2a/discovery/{agent_id}",
    response_model=DiscoveryA2aResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    summary="Post discovery information for a2a agent by agent id",
)
async def get_discovery_a2a_info(agent_id: str, request: Request) -> DiscoveryA2aResponse:
    logger.info("Executing get_discovery_a2a_info endpoint : agent_id=%s", agent_id)
    with tracer.start_as_current_span("router.get_discovery_a2a_info") as span:
        try:
            repo = request.app.state.container.server_repository
            a2a_repo = request.app.state.container.a2a_agent_repository
            use_case = DiscoveryServicesUseCase(repo, a2a_repo)

            result = await use_case.post_discovery_a2a_service(agent_id)
            if result is None:
                raise NotFoundError(message=f"A2A agent {agent_id} not found")
            return result

        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error retrieving registered a2a agent: {e}")
            raise ServiceError(message=f"Error retrieving registered a2a agent: {e}") from e
        
#----------------------------------------------
# Catalog Search
@router.post(
    "/v1/catalog/search",
    response_model=CatalogSearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Search catalog",
)
async def search_catalog(payload: CatalogSearchRequest, request: Request) -> CatalogSearchResponse:
    logger.info("Executing search_catalog endpoint : payload=%s", payload)
    with tracer.start_as_current_span("router.search_catalog") as span:
        try:
            repo = request.app.state.container.server_repository
            use_case = RegisteredServicesUseCase(repo)

            result = await use_case.search_registered_services(payload)
            message = f"Service search completed successfully"
            return CatalogSearchResponse(
                message=message,
                results=[
                    CatalogSearchResult(**item) if isinstance(item, dict) else item
                    for item in (result or [])
                ],
            )
        
        except AppError:
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error(f"Error searching catalog: {e}")
            raise ServiceError(message=f"Error searching catalog: {e}") from e
