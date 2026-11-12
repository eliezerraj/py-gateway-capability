import json
import logging
from typing import Any, Dict

import httpx2
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from opentelemetry import trace

from mcp_gateway.config.settings import settings
from mcp_gateway.domain.model.context import get_security_context

#---------------------------------
# Configure logging
#---------------------------------
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)


def _build_mcp_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    security = get_security_context()
    if security is None:
        return headers

    if security.auth_token:
        headers["Authorization"] = f"Bearer {security.auth_token}"
    if security.x_request_id:
        headers["X-Request-ID"] = security.x_request_id

    return headers


async def mcp_tool_execution(payload: Dict) -> Dict:
    with tracer.start_as_current_span("mcp.tool_execution") as span:
        logger.info("Executing tool for product with payload: %s", payload)
        mcp_server_inventory_url = settings.MCP_SERVER_INVENTORY_URL

        try:
            async with streamable_http_client(mcp_server_inventory_url) as (read_stream, write_stream):
                logger.info("Connected to MCP server at URL: %s", mcp_server_inventory_url)

            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tool_uri = "patch_product"
                logger.info("Executing tool for URI: %s", tool_uri)

                result = await session.call_tool(tool_uri, payload)
                return result.contents[0].text
        except Exception as e:
            logger.error("Exception occurred while executing tool for product with payload: %s, error: %s", payload, e)
            raise e

async def mcp_resource_fetcher(resource_uri: str, mcp_server_url: str) -> str:
    logger.info("Fetching resource for URI: %s from MCP server at URL: %s", resource_uri, mcp_server_url)

    headers = _build_mcp_headers()
    if "X-Request-ID" in headers:
        logger.info("Fetching resource for URI: %s with x-request-id: %s ", resource_uri, headers["X-Request-ID"])

    captured = {}

    async def capture_error_response(response):
        if response.status_code >= 400:
            await response.aread()
            captured.update(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=response.text,
            )

    with tracer.start_as_current_span("mcp.mcp_resource_fetcher") as span:
        try:
            async with httpx2.AsyncClient(headers=headers, event_hooks={"response": [capture_error_response]}) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.read_resource(resource_uri)
                        return result.contents[0].text

        except Exception as e:
            logger.error("Exception occurred while fetching resource for URI: %s, error: %s", resource_uri, e)

            status_code = captured.get("status_code", 500)

            if status_code == 401:
                span.set_attribute("http.status_code", status_code)
                www_authenticate = captured["headers"].get("www-authenticate")
                logger.warning("Response status_code: %s, www-authenticate: %s, body: %s", status_code, www_authenticate, captured["body"])
                return json.dumps({
                    "status_code": 401,
                    "www_authenticate": www_authenticate,
                    "error": "Unauthorized"
                })

            logger.warning("Response status_code: %s", status_code)
            span.set_attribute("http.status_code", status_code)
            raise e

async def mcp_resources_discovery(mcp_server_url: str) -> list[dict[str, Any]]:
    logger.info("Discovering MCP resources from URL: %s", mcp_server_url)
    headers = _build_mcp_headers()

    with tracer.start_as_current_span("mcp.mcp_resources_discovery"):
        try:
            async with httpx2.AsyncClient(headers=headers) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        if initialized.capabilities.resources is None:
                            return []

                        resources: list[dict[str, Any]] = []
                        cursor = None
                        while True:
                            page = await session.list_resources(
                                params=types.PaginatedRequestParams(cursor=cursor)
                                if cursor is not None
                                else None
                            )
                            resources.extend(
                                resource.model_dump(mode="json", by_alias=True, exclude_none=True)
                                for resource in page.resources
                            )
                            cursor = page.next_cursor
                            if not cursor:
                                break

                        return resources
        except Exception as e:
            logger.error("Exception occurred while discovering MCP resources from URL: %s, error: %s", mcp_server_url, e)
            raise

async def mcp_tools_discovery(mcp_server_url: str) -> list[dict[str, Any]]:
    logger.info("Discovering MCP tools from URL: %s", mcp_server_url)
    headers = _build_mcp_headers()

    with tracer.start_as_current_span("mcp.mcp_tools_discovery"):
        try:
            async with httpx2.AsyncClient(headers=headers) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        if initialized.capabilities.tools is None:
                            return []

                        tools: list[dict[str, Any]] = []
                        cursor = None
                        while True:
                            page = await session.list_tools(
                                params=types.PaginatedRequestParams(cursor=cursor)
                                if cursor is not None
                                else None
                            )
                            tools.extend(
                                tool.model_dump(mode="json", by_alias=True, exclude_none=True)
                                for tool in page.tools
                            )
                            cursor = page.next_cursor
                            if not cursor:
                                break

                        return tools
        except Exception as e:
            logger.error("Exception occurred while discovering MCP tools from URL: %s, error: %s", mcp_server_url, e)
            raise

async def mcp_prompts_discovery(mcp_server_url: str) -> list[dict[str, Any]]:
    logger.info("Discovering MCP prompts from URL: %s", mcp_server_url)
    headers = _build_mcp_headers()

    with tracer.start_as_current_span("mcp.mcp_prompts_discovery"):
        try:
            async with httpx2.AsyncClient(headers=headers) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        if initialized.capabilities.prompts is None:
                            return []

                        prompts: list[dict[str, Any]] = []
                        cursor = None
                        while True:
                            page = await session.list_prompts(
                                params=types.PaginatedRequestParams(cursor=cursor)
                                if cursor is not None
                                else None
                            )
                            prompts.extend(
                                prompt.model_dump(mode="json", by_alias=True, exclude_none=True)
                                for prompt in page.prompts
                            )
                            cursor = page.next_cursor
                            if not cursor:
                                break

                        return prompts
        except Exception as e:
            logger.error("Exception occurred while discovering MCP prompts from URL: %s, error: %s", mcp_server_url, e)
            raise

async def mcp_resource_templates_discovery(mcp_server_url: str) -> list[dict[str, Any]]:
    logger.info("Discovering MCP resource templates from URL: %s", mcp_server_url)
    headers = _build_mcp_headers()

    with tracer.start_as_current_span("mcp.mcp_resource_templates_discovery"):
        try:
            async with httpx2.AsyncClient(headers=headers) as http_client:
                async with streamable_http_client(mcp_server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        initialized = await session.initialize()
                        if initialized.capabilities.resources is None:
                            return []

                        resource_templates: list[dict[str, Any]] = []
                        cursor = None
                        while True:
                            page = await session.list_resource_templates(
                                params=types.PaginatedRequestParams(cursor=cursor)
                                if cursor is not None
                                else None
                            )
                            templates = getattr(page, "resourceTemplates", None)
                            if templates is None:
                                templates = getattr(page, "resource_templates", [])
                            resource_templates.extend(
                                resource_template.model_dump(mode="json", by_alias=True, exclude_none=True)
                                for resource_template in templates
                            )
                            cursor = page.next_cursor
                            if not cursor:
                                break

                        return resource_templates
        except Exception as e:
            logger.error(
                "Exception occurred while discovering MCP resource templates from URL: %s, error: %s",
                mcp_server_url,
                e,
            )
            raise
