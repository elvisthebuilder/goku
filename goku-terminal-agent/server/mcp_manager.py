import os
import httpx
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class MCPManager:
    def __init__(self):
        self.servers = {
            "git": os.getenv("MCP_GIT_URL", "http://mcp-git:8080"),
            "search": os.getenv("MCP_SEARCH_URL", "http://mcp-search:8080"),
        }

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        all_tools = []
        async with httpx.AsyncClient() as client:
            for name, url in self.servers.items():
                try:
                    response = await client.get(f"{url}/tools", timeout=5.0)
                    if response.status_code == 200:
                        tools = response.json()
                        # Namespace tools to avoid collisions
                        for tool in tools:
                            tool["name"] = f"mcp_{name}__{tool['name']}"
                        all_tools.extend(tools)
                except Exception as e:
                    logger.error(f"Error fetching tools from MCP server {name}: {str(e)}")
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, args: Dict[str, Any]) -> Any:
        url = self.servers.get(server_name)
        if not url:
            return f"Error: MCP server {server_name} not found."

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{url}/call",
                    json={"name": tool_name, "arguments": args},
                    timeout=30.0
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    return f"Error from MCP server: {response.text}"
            except Exception as e:
                logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
                return f"Error executing MCP tool: {str(e)}"

mcp_manager = MCPManager()
