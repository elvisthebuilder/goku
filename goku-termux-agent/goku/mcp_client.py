import os
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    """
    Client for connecting to Model Context Protocol (MCP) servers.
    Manages the connection and tool execution for a single server.
    """
    def __init__(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.session: Optional[ClientSession] = None
        self._exit_stack = None
        self.tools_cache = []

    async def connect(self):
        """Connects to the MCP server via stdio."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **self.env}
        )
        
        try:
            # We need to manage the context manager manually to keep connection alive
            from contextlib import AsyncExitStack
            self._exit_stack = AsyncExitStack()
            
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            
            # Cache available tools
            result = await self.session.list_tools()
            self.tools_cache = result.tools
            return True
        except Exception as e:
            print(f"Failed to connect to MCP server '{self.name}': {e}")
            return False

    async def list_tools_schema(self) -> List[Dict[str, Any]]:
        """Returns tools in OpenAI/HF function calling format."""
        if not self.session:
            return []
            
        schemas = []
        for tool in self.tools_cache:
            schema = {
                "type": "function",
                "function": {
                    "name": f"{self.name}__{tool.name}", # Namespaced: server__tool
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            schemas.append(schema)
        return schemas

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Calls a tool on the server."""
        if not self.session:
            return f"Error: MCP server '{self.name}' not connected."
        
        # Remove namespace prefix if present
        actual_tool_name = tool_name
        if tool_name.startswith(f"{self.name}__"):
            actual_tool_name = tool_name[len(f"{self.name}__"):]
            
        try:
            result = await self.session.call_tool(actual_tool_name, arguments)
            # Format result content
            output = []
            for content in result.content:
                if content.type == "text":
                    output.append(content.text)
                elif content.type == "image":
                    output.append(f"[Image: {content.mimeType}]")
                elif content.type == "resource":
                     output.append(f"[Resource: {content.uri}]")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error executing tool '{actual_tool_name}' on '{self.name}': {str(e)}"

    async def close(self):
        """Closes the connection."""
        if self._exit_stack:
            await self._exit_stack.aclose()
