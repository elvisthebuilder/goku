import asyncio
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server_runner
import mcp.types as types
from duckduckgo_search import DDGS

# Initialize Server
app = Server("internet")

# Tools
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_web",
            description="Search the web for information using DuckDuckGo. Use this to find current events, documentation, or general knowledge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="read_webpage",
            description="Read the text content of a webpage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to read"}
                },
                "required": ["url"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_web":
        query = arguments.get("query")
        if not query:
            return [types.TextContent(type="text", text="Error: query required")]
        
        try:
            # Run sync DDGS in thread
            results = await asyncio.to_thread(_search_ddg, query)
            return [types.TextContent(type="text", text=results)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Search error: {e}")]

    elif name == "read_webpage":
        url = arguments.get("url")
        if not url:
            return [types.TextContent(type="text", text="Error: url required")]
        
        try:
            # Basic fetch
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                # Simple text extraction (could use readability in future)
                text = resp.text[:8000] # Limit size
                return [types.TextContent(type="text", text=f"Source: {url}\n\n{text}")]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Fetch error: {e}")]

    raise ValueError(f"Tool {name} not found")

def _search_ddg(query):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
        formatted = []
        for r in results:
            formatted.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n---")
        if not formatted:
            return "No results found."
        return "\n".join(formatted)

async def main():
    async with stdio_server_runner(app) as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
