import pytest
from fastapi.testclient import TestClient

from punctual.app import create_app
from punctual.tasks.service import TaskService


@pytest.fixture
def store(tmp_path):
    service = TaskService(str(tmp_path / "tasks.db"))
    yield service
    service.database.engine.dispose()


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "api.db"), "secret")) as client:
        yield client


@pytest.fixture
def auth():
    return {"Authorization": "Bearer secret"}
