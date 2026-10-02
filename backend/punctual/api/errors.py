import json

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from ..tasks.errors import Conflict


def install_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # Do not echo credentials or malformed Unicode from the submitted input.
        # Even error locations may contain invalid Unicode in extra field names.
        detail = [
            {key: error[key] for key in ("type", "loc", "msg")}
            for error in exc.errors()
        ]
        return Response(
            json.dumps({"detail": detail}, ensure_ascii=True),
            status_code=422,
            media_type="application/json",
        )

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        error = {"code": exc.code, "message": exc.message}
        if getattr(exc, "details", None) is not None:
            error["details"] = exc.details
        return JSONResponse(
            {"error": error},
            status_code=exc.status,
        )
