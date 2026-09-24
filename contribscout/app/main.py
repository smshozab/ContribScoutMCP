import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .mcp.tools.analysis import build_contribution_plan, find_contribution_opportunities, pre_contribution_check, analyze_repository_tool
from .mcp.tools.files import get_file, search_repository_markers
from .mcp.tools.issues import get_issue, list_issues
from .mcp.tools.pulls import list_pull_requests
from .mcp.tools.repository import get_recent_commits, get_repository, get_repository_tree
from .config import get_settings
from .oauth import JwtTokenVerifier
from .security import McpAccessMiddleware, validate_remote_auth

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
HOST = os.getenv("MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("PORT") or os.getenv("MCP_PORT") or "8000")
settings = get_settings()
oauth_kwargs = {}
if settings.oauth_enabled:
    from mcp.server.auth.settings import AuthSettings

    oauth_kwargs = {
        "auth": AuthSettings(
            issuer_url=settings.mcp_oauth_issuer_url,
            resource_server_url=settings.mcp_oauth_resource_url,
            validate_token_resource=False,
            required_scopes=settings.mcp_oauth_required_scopes,
        ),
        "token_verifier": JwtTokenVerifier(
            issuer=str(settings.mcp_oauth_issuer_url),
            audience=settings.mcp_oauth_audience,
            required_scopes=settings.mcp_oauth_required_scopes,
        ),
    }
mcp = FastMCP(
    "ContribScout",
    instructions=(
        "Read-only assistant for public GitHub repositories. Use structured GitHub data and deterministic "
        "heuristics to distinguish OFFICIAL_ISSUE items from DISCOVERED_OPPORTUNITY items. "
        "Do not imply access to a user's ChatGPT history or guarantee maintainer acceptance."
    ),
    host=HOST,
    port=PORT,
    **oauth_kwargs,
)

for tool in (get_repository, get_repository_tree, get_file, list_issues, get_issue, list_pull_requests, get_recent_commits, search_repository_markers, analyze_repository_tool, find_contribution_opportunities, pre_contribution_check, build_contribution_plan):
    public_name = "analyze_repository" if tool is analyze_repository_tool else None
    tool_meta = (
        {"securitySchemes": [{"type": "oauth2", "scopes": settings.mcp_oauth_required_scopes}]}
        if settings.oauth_enabled
        else None
    )
    mcp.tool(
        name=public_name,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True, destructiveHint=False),
        meta=tool_meta,
    )(tool)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        token = os.getenv("MCP_AUTH_TOKEN", "").strip()
        validate_remote_auth(HOST, token, oauth_enabled=settings.oauth_enabled)
        import uvicorn

        app = McpAccessMiddleware(
            mcp.streamable_http_app(),
            token=None if settings.oauth_enabled else (token or None),
            oauth_enabled=settings.oauth_enabled,
            requests_per_minute=settings.mcp_rate_limit_per_minute,
        )
        logger = logging.getLogger("contribscout.server")
        logger.info("Starting Streamable HTTP MCP server on %s:%s", HOST, PORT)
        uvicorn.run(
            app,
            host=HOST,
            port=PORT,
            limit_concurrency=100,
            timeout_keep_alive=15,
            server_header=False,
        )
    elif transport == "stdio":
        mcp.run(transport="stdio")
    else:
        raise ValueError("MCP_TRANSPORT must be stdio or streamable-http")


if __name__ == "__main__":
    main()
