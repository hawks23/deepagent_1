"""Shared MCP configuration and a standalone tool-discovery check."""
import asyncio
from contextlib import asynccontextmanager

from langchain.mcp import MCPAdapter

# Add each server here using a unique name. Names prefix its tools.
MCP_SERVERS = {
    "langchain_docs": {"url": "https://docs.langchain.com/mcp"},
    "fastmcp_docs": {"url": "https://gofastmcp.com/mcp"},
    "perfume-finder": {"url": "https://mcp.10ml.com/mcp"}
}


@asynccontextmanager
async def load_mcp_tools():
    """Discover all configured tools and keep connections open during use."""
    async with MCPAdapter({"mcpServers": MCP_SERVERS}) as adapter:
        tools = await adapter.list_tools()
        yield tools


async def main():
    async with load_mcp_tools() as tools:
        print(f"Loaded {len(tools)} tools from {len(MCP_SERVERS)} servers")
        for tool in tools:
            print(f"\n{tool.name}: {tool.description}")
            print(f"Arguments: {tool.args}")


if __name__ == "__main__":
    asyncio.run(main())
