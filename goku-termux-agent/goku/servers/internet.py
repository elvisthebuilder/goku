import asyncio
import json
import httpx
import os
import sys

# Hack to import config from parent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Initialize Server
app = Server("internet")

BRAVE_API_KEY = config.get_brave_key()

# Tools
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_web",
            description="Search the web for information using Brave Search. Use this to find current events, documentation, or general knowledge.",
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
            # Use active provider
            active_provider = config.get_active_search_provider()
            
            if active_provider == "brave":
                results = await _search_brave(query)
            elif active_provider == "google":
                results = await _search_google(query)
            elif active_provider == "bing":
                results = await _search_bing(query)
            elif active_provider == "duckduckgo":
                results = await _search_ddg(query)
            else:
                results = f"Error: Unknown search provider '{active_provider}'"
                
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

async def _search_brave(query, count=5):
    api_key = config.get_search_token("brave")
    if not api_key:
        return "Error: Brave Search API key not configured. Use `/token brave <key>`."

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    params = {"q": query, "count": count}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        items = data.get("web", {}).get("results", [])
        if not items:
            return "No results found."

        for item in items:
            title = item.get("title", "No Title")
            link = item.get("url", "")
            snippet = item.get("description", "")
            results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")
        return "\n".join(results)

async def _search_google(query, count=5):
    api_key = config.get_search_token("google")
    if not api_key:
        return "Error: Google API key not configured. Use `/token google <KEY>`."
    
    cx = None
    if ":" in api_key:
        parts = api_key.split(":")
        api_key = parts[0]
        cx = parts[1]
    
    if not cx:
         return "Error: Google Search requires a Context ID (CX). Please set token as `API_KEY:CX_ID`."

    url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": cx, "q": query, "num": count}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        items = data.get("items", [])
        if not items:
            return "No results found."

        for item in items:
            title = item.get("title", "No Title")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")
        return "\n".join(results)

async def _search_bing(query, count=5):
    api_key = config.get_search_token("bing")
    if not api_key:
        return "Error: Bing API key not configured. Use `/token bing <key>`."
        
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    params = {"q": query, "count": count}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        items = data.get("webPages", {}).get("value", [])
        
        if not items:
             return "No results found."
        
        for item in items:
            title = item.get("name", "No Title")
            link = item.get("url", "")
            snippet = item.get("snippet", "")
            results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")
        return "\n".join(results)

async def _search_ddg(query, count=5):
    # Use the duckduckgo_search library which is installed
    from duckduckgo_search import DDGS
    
    def run_ddg():
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=count))
            formatted = []
            for r in results:
                formatted.append(f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}\n---")
            if not formatted:
                return "No results found."
            return "\n".join(formatted)

    return await asyncio.to_thread(run_ddg)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
