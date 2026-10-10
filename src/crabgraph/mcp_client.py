import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from crabgraph.settings import ROOT


async def call_mcp_async(name: str, arguments: dict):
    params = StdioServerParameters(command=sys.executable, args=["-m", "crabgraph.mcp_server"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError("MCP tool failed")
            structured = result.structuredContent
            if structured:
                return json.dumps(structured.get("result", structured), ensure_ascii=False)
            texts = [c.text for c in result.content if hasattr(c, "text")]
            try:
                values = [json.loads(t) for t in texts]
                return json.dumps(values[0] if len(values) == 1 else values, ensure_ascii=False)
            except ValueError:
                return json.dumps({"text": "\n".join(texts)}, ensure_ascii=False)


def call_mcp(name: str, arguments: dict):
    return asyncio.run(call_mcp_async(name, arguments))


async def inspect_mcp():
    params = StdioServerParameters(command=sys.executable, args=["-m", "crabgraph.mcp_server"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            result = await session.call_tool("analyze_pond_csv", {"csv_text": (ROOT / "examples" / "pond_records.csv").read_text(encoding="utf-8")})
            return {"tools": [t.name for t in tools.tools], "resources": [str(r.uri) for r in resources.resources],
                    "statistics": json.loads(result.content[0].text), "is_error": bool(result.isError)}
