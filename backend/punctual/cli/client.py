import json
from dataclasses import dataclass
from urllib.parse import quote

import httpx
import typer


@dataclass
class Client:
    url: str
    api_key: str
    json_output: bool = False

    def request(self, method: str, path: str, *, resource="tasks", emit=True, **kwargs):
        try:
            if not self.api_key:
                raise ValueError("Set PUNCTUAL_API_KEY or pass --api-key")
            response = httpx.request(
                method,
                self.url.rstrip("/") + f"/api/{resource}" + path,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
                **kwargs,
            )
            data = response.json()
            if response.is_error:
                error = data.get(
                    "error",
                    {
                        "code": "validation_error",
                        "message": str(data.get("detail", data)),
                    },
                )
                self.emit({"error": error})
                raise typer.Exit(3 if response.status_code == 409 else 1)
            if emit:
                self.emit(data)
            return data
        except (httpx.HTTPError, ValueError) as exc:
            self.emit({"error": {"code": "client_error", "message": str(exc)}})
            raise typer.Exit(1) from exc

    @staticmethod
    def task_path(reference: str) -> str:
        try:
            return f"/{int(reference)}"
        except ValueError:
            return f"/by-key/{quote(reference, safe='')}"

    def task_id(self, reference: str) -> int:
        """Resolve identity only; never adopt a lookup's revision or lease metadata."""
        try:
            return int(reference)
        except ValueError:
            return self.request("GET", self.task_path(reference), emit=False)["id"]

    def board_id(self, reference: str) -> int:
        try:
            return int(reference)
        except ValueError:
            boards = self.request("GET", "", resource="boards", emit=False)
            for board in boards:
                if board["prefix"] == reference:
                    return board["id"]
            self.emit({"error": {"code": "not_found", "message": "Board not found"}})
            raise typer.Exit(1) from None

    def emit(self, data):
        if self.json_output:
            typer.echo(json.dumps(data))
        elif isinstance(data, list) and all("title" in item for item in data):
            for item in data:
                typer.echo(
                    f"#{item['id']}  [{item['status']}] {item['title']}  "
                    f"@{item['assignee'] or 'unassigned'}  r{item['revision']}"
                )
        else:
            typer.echo(json.dumps(data, indent=2))
