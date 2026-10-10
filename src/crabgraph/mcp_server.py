"""Actual stdio MCP tools, usable from any MCP-compatible client."""
import json

from mcp.server.fastmcp import FastMCP

from crabgraph import business_tools
from crabgraph.business_tools import search_reference_images as image_search
from crabgraph.pond import analyze_csv
from crabgraph.retrieval import LightRAGClient
from crabgraph.settings import Settings
from crabgraph.store import Store
from crabgraph.tool_registry import catalog, require_enabled

mcp = FastMCP("CrabGraph 青蟹知识工具")


@mcp.tool()
def search_crab_knowledge(question: str, mode: str = "mix") -> dict:
    """Retrieve cited mud-crab evidence from the migrated local LightRAG database."""
    if not question.strip() or len(question) > 4000:
        raise ValueError("Question length must be 1–4000")
    settings = Settings.from_env()
    if settings.lightrag_url != "http://127.0.0.1:9622":
        raise ValueError("Only the migrated project instance is allowed")
    return LightRAGClient(settings.lightrag_url, settings.lightrag_api_key, use_graph=Store().graph_enabled()).search(question, mode)["data"]


@mcp.tool()
def analyze_pond_csv(csv_text: str) -> dict:
    """Compute statistics on user-supplied pond records without assuming suitability thresholds."""
    require_enabled("terminal")
    if len(csv_text.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("CSV too large")
    return analyze_csv(csv_text)


@mcp.resource("crabgraph://capabilities")
def capabilities() -> str:
    return json.dumps({"domain": "青蟹养殖", "tools": [t["mcp"] for t in catalog(Store())], "enabled_tools": [t["mcp"] for t in catalog(Store()) if t["enabled"]],
                       "knowledge_instance": "project copy :9622", "transport": "stdio"}, ensure_ascii=False)


@mcp.tool()
def search_reference_images(query: str) -> list[dict]:
    """Search Wikimedia Commons reference images with source pages and license information."""
    require_enabled("mcp_images")
    return image_search(query)


@mcp.tool()
def search_public_literature(query: str) -> list[dict]:
    """Search Crossref online for scholarly metadata, DOIs and paper links."""
    require_enabled("literature")
    return business_tools.search_literature(query)


@mcp.tool()
def fetch_research_page(url: str) -> dict:
    """Read a public research webpage from the supported research domains."""
    require_enabled("webpage")
    return business_tools.read_public_page(url)


@mcp.tool()
def download_research_pdf(url: str) -> dict:
    """Download an allowed public PDF to the project's resources directory."""
    require_enabled("download")
    return business_tools.download_public_pdf(url)


@mcp.tool()
def save_note(text: str) -> dict:
    """Save a Markdown note in the project's resources directory."""
    require_enabled("note")
    return business_tools.save_research_note(text)


if __name__ == "__main__":
    mcp.run(transport="stdio")
