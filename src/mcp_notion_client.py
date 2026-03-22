"""
src/mcp_notion_client.py
Python MCP client for Notion operations via @notionhq/notion-mcp-server.

This module spawns the Node.js Notion MCP server as a subprocess and communicates
with it via the mcp Python package (stdio protocol). All Notion operations are routed
through MCP tools instead of direct SDK calls.

MCP Tool Names (from Notion OpenAPI operationIds):
  - API-retrieve-a-database
  - API-query-a-database
  - API-create-a-database
  - API-create-a-page
  - API-retrieve-block-children
"""

import os
import json
import asyncio
from typing import Any


async def _run_notion_tool(tool_name: str, arguments: dict) -> Any:
    """Run a Notion MCP tool asynchronously.

    Args:
        tool_name: Name of the MCP tool (e.g., "API-retrieve-a-database")
        arguments: Arguments for the tool (path params + body)

    Returns:
        The response from the Notion MCP server (parsed JSON)

    Raises:
        RuntimeError: If the MCP tool returns an error
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    api_key = os.environ.get("NOTION_API_KEY", "")
    openapi_headers = json.dumps({
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28"
    })

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={**dict(os.environ), "OPENAPI_MCP_HEADERS": openapi_headers},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            if result.isError:
                raise RuntimeError(f"Notion MCP tool {tool_name!r} returned an error")

            for item in result.content:
                if hasattr(item, "text"):
                    return json.loads(item.text)

    return {}


def call_notion_mcp(tool_name: str, arguments: dict) -> Any:
    """Synchronous wrapper to call a Notion MCP tool.

    This uses asyncio.run() to execute the async MCP call, which is safe
    to use from both the main thread and daemon threads.

    Args:
        tool_name: Name of the MCP tool
        arguments: Arguments for the tool

    Returns:
        The response from the Notion MCP server
    """
    return asyncio.run(_run_notion_tool(tool_name, arguments))
