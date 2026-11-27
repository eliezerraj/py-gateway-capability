import logging
from urllib.parse import urlsplit

from opentelemetry import trace

from mcp_gateway.config.settings import settings
from mcp_gateway.domain.exceptions import NotFoundError, ServiceError
from mcp_gateway.domain.model.embedding import EmbeddingRequest, EmbeddingResponse
from mcp_gateway.infrastructure.adapter.http.http_client import HttpAdapter

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

TEI_MODEL_ID = "tei"

def _resolve_model_endpoint(model_id: str) -> tuple[str, str]:
    match model_id:
        case "tei":
            endpoint = settings.EMBEDDED_SERVICE_TEI_ENDPOINT
            resolved_model_id = TEI_MODEL_ID
        case _:
            raise NotFoundError(message=f"Embedding model {model_id} not supported")

    if not endpoint:
        raise ServiceError(message=f"Endpoint for embedding model {model_id} is not configured")

    return endpoint, resolved_model_id

def _split_endpoint(endpoint: str) -> tuple[str, str]:
    # Split so HttpAdapter does not append a trailing slash to the model URL.
    parts = urlsplit(endpoint)
    base_url = f"{parts.scheme}://{parts.netloc}"
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return base_url, path

class EmbeddedServiceUseCase:
    def __init__(self, http_adapter: HttpAdapter | None = None):
        logger.info("Initializing EmbeddedServiceUseCase")
        self.http_adapter = http_adapter or HttpAdapter()

    async def get_embedding(self, payload: EmbeddingRequest) -> EmbeddingResponse:
        logger.info("Executing get_embedding with model_id=%s", payload.model_id)

        with tracer.start_as_current_span("usecase.get_embedding") as span:
            endpoint, model_id = _resolve_model_endpoint(payload.model_id)
            base_url, path = _split_endpoint(endpoint)
            span.set_attribute("embedding.model_id", model_id)

            model_payload = {
                "inputs": payload.inputs,
                "normalize": payload.normalize,
                "truncate": payload.truncate,
                "truncation_direction": payload.truncation_direction,
            }

            response = await self.http_adapter.post(
                base_url=base_url,
                path=path,
                payload=model_payload,
            )

            if (
                not isinstance(response, list)
                or not response
                or not isinstance(response[0], list)
                or not response[0]
            ):
                raise ServiceError(message=f"Invalid or empty response from embedding model {model_id}")

            embedding = response[0]
            span.set_attribute("embedding.dimensions", len(embedding))

            return EmbeddingResponse(
                embedding=embedding,
                model_id=model_id,
                dimensions=len(embedding),
                normalized=payload.normalize,
            )
