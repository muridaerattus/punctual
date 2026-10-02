"""FastMCP result adaptation: schema-checked payloads and protocol errors."""

from fastmcp.exceptions import NotFoundError, ToolError, ValidationError
from fastmcp.server.middleware import Middleware
from fastmcp.tools import ToolResult
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from ..tasks.errors import Conflict


def error_result(code, message, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    payload = {"ok": False, "error": error}
    return ToolResult(structured_content=payload, is_error=True)


def result(payload_type, call, *args, summary=None, **kwargs):
    try:
        data = call(*args, **kwargs)
    except Conflict as exc:
        return error_result(exc.code, exc.message, getattr(exc, "details", None))
    # Project away private fields before either serialization path.
    adapter = TypeAdapter(payload_type)
    data = adapter.dump_python(adapter.validate_python(data), mode="json")
    payload = {"ok": True, "data": data}
    if summary is not None:
        payload["summary"] = summary(data)
    # The first text block stays the JSON envelope for older clients.
    return ToolResult(structured_content=payload)


class ErrorEnvelopeMiddleware(Middleware):
    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except ValidationError as exc:
            cause = exc.__cause__
            details = None
            if isinstance(cause, PydanticValidationError):
                details = {
                    "fields": [
                        {"path": list(item["loc"]), "type": item["type"]}
                        for item in cause.errors(
                            include_input=False, include_context=False
                        )
                    ]
                }
            return error_result(
                "invalid_arguments", "Arguments do not match the tool schema", details
            )
        except NotFoundError:
            return error_result("not_found", "Tool not found")
        except ToolError:
            return error_result("internal_error", "Tool execution failed")
