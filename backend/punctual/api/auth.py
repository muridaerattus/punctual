import secrets

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .oidc import PUBLIC_AUTH_PATHS, BrowserAuth


def install_authentication(app: FastAPI, key: str, browser: BrowserAuth):
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
        if protected and path not in PUBLIC_AUTH_PATHS:
            supplied = request.headers.get("authorization", "")
            bearer = secrets.compare_digest(supplied.encode(), f"Bearer {key}".encode())
            cookie = (
                not supplied
                and not path.startswith("/mcp")
                and browser.session(request)
            )
            if not bearer and not cookie:
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
            if (
                cookie
                and request.method not in ("GET", "HEAD", "OPTIONS")
                and not browser.csrf_valid(request)
            ):
                return JSONResponse(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Same-origin request required",
                        }
                    },
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response
