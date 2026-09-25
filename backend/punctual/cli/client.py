import json
from dataclasses import dataclass

import httpx
import typer


@dataclass
class Client:
    url: str
    api_key: str
    json_output: bool = False

    def request(self, method: str, path: str, **kwargs):
        try:
            if not self.api_key:
                raise ValueError("Set PUNCTUAL_API_KEY or pass --api-key")
            response = httpx.request(
                method,
                self.url.rstrip("/") + "/api/tasks" + path,
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
            self.emit(data)
        except (httpx.HTTPError, ValueError) as exc:
            self.emit({"error": {"code": "client_error", "message": str(exc)}})
            raise typer.Exit(1) from exc

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
