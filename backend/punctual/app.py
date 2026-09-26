from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.auth import install_authentication
from .api.boards import board_router
from .api.errors import install_error_handlers
from .api.tasks import task_router
from .config import Settings
from .mcp.server import create_mcp
from .tasks.service import TaskService


def create_app(db_path: str | None = None, api_key: str | None = None):
    overrides = {}
    if db_path is not None:
        overrides["db"] = db_path
    if api_key is not None:
        overrides["api_key"] = api_key
    settings = Settings(**overrides)
    if not settings.api_key:
        raise RuntimeError("Set PUNCTUAL_API_KEY before starting Punctual")

    tasks = TaskService(settings.db)
    mcp = create_mcp(tasks)
    mcp_app = mcp.http_app(
        path="/",
        stateless_http=True,
        json_response=True,
        host_origin_protection=True,
        allowed_hosts=settings.host_list,
        allowed_origins=settings.origin_list,
    )

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with mcp_app.lifespan(app):
                yield
        finally:
            tasks.database.engine.dispose()

    app = FastAPI(title="Punctual", lifespan=lifespan)
    app.state.tasks = tasks
    app.state.mcp = mcp
    install_authentication(app, settings.api_key)
    install_error_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(task_router(tasks))
    app.include_router(board_router(tasks))
    app.mount("/mcp", mcp_app)
    if settings.static.is_dir():
        app.mount(
            "/", StaticFiles(directory=settings.static, html=True), name="frontend"
        )
    return app
