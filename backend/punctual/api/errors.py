from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..tasks.errors import Conflict


def install_error_handlers(app: FastAPI):
    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=exc.status,
        )
