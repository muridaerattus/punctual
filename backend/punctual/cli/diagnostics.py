"""Read-only connection checks shared by the CLI and deployment."""

import httpx

VERSION = "2026-07-28"
TOOLS = {
    "list_boards",
    "create_board",
    "get_task_by_key",
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "delete_task",
    "claim_task",
    "renew_lease",
    "release_lease",
    "force_release_lease",
}


def diagnose(url: str, api_key: str, host: str | None = None):
    checks = []

    def fail(code, message):
        return {
            "ok": False,
            "checks": checks,
            "error": {"code": code, "message": message},
        }

    if not api_key:
        return fail(
            "missing_key", "Set PUNCTUAL_API_KEY in the client process environment."
        )
    headers = {"Authorization": f"Bearer {api_key}"}
    if host:
        headers["Host"] = host
    for name, path in [
        ("health", "/health"),
        ("frontend", "/"),
        ("authentication", "/api/tasks"),
        ("server/discover", "/mcp/"),
        ("tools/list", "/mcp/"),
    ]:
        mcp = path == "/mcp/"
        kwargs = {}
        request_headers = dict(headers)
        if mcp:
            request_headers.update(
                {
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": VERSION,
                    "Mcp-Method": name,
                }
            )
            kwargs["json"] = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": name,
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": VERSION,
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
            }
        try:
            response = httpx.request(
                "POST" if mcp else "GET",
                url.rstrip("/") + path,
                headers=request_headers,
                timeout=5,
                **kwargs,
            )
        except httpx.HTTPError:
            return fail(
                "connection_failed",
                f"{name}: connection failed; check URL, DNS, TLS and server availability.",
            )
        status = response.status_code
        errors = {
            401: (
                "unauthorized",
                "Check that the client key matches the server PUNCTUAL_API_KEY.",
            ),
            403: ("forbidden", "Check server access and origin policies."),
            404: (
                "wrong_endpoint",
                "Use the server base URL; MCP must be mounted at /mcp/.",
            ),
            405: (
                "wrong_endpoint",
                "MCP requests must target /mcp/, not the frontend URL.",
            ),
            421: (
                "disallowed_host",
                "Add the client hostname:port to PUNCTUAL_ALLOWED_HOSTS and recreate the server container.",
            ),
        }
        if status in errors:
            code, message = errors[status]
            return fail(code, f"{name}: HTTP {status}. {message}")
        if status != 200:
            return fail(
                "http_error",
                f"{name}: HTTP {status}; check endpoint and server configuration.",
            )
        if mcp:
            try:
                data = response.json()
                result = data["result"]
                if name == "server/discover":
                    if VERSION not in result.get("supportedVersions", []):
                        return fail(
                            "unsupported_protocol",
                            f"Server must advertise MCP {VERSION} via server/discover.",
                        )
                elif not TOOLS <= {tool["name"] for tool in result["tools"]}:
                    return fail(
                        "missing_tools",
                        "MCP catalog is missing expected Punctual tools.",
                    )
            except (ValueError, KeyError, TypeError, AttributeError):
                return fail(
                    "invalid_mcp_response",
                    f"{name}: invalid MCP response; check endpoint and MCP {VERSION} support.",
                )
        checks.append({"name": name, "ok": True})
    return {"ok": True, "checks": checks}
