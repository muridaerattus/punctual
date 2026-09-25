import secrets

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def install_authentication(app: FastAPI, key: str):
    @app.middleware("http")
    async def authenticate(request, call_next):
        path = request.url.path
        protected = path in (
            "/api",
            "/mcp",
            "/docs",
            "/openapi.json",
            "/redoc",
        ) or path.startswith(("/api/", "/mcp/"))
        if protected:
            supplied = request.headers.get("authorization", "")
            if not secrets.compare_digest(supplied.encode(), f"Bearer {key}".encode()):
                return JSONResponse(
                    {
                        "error": {
                            "code": "unauthorized",
                            "message": "Valid API key required",
                        }
                    },
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
