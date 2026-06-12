import base64
import json
from typing import Any

import pytest


def task_header(
    task_id: str = "task-1",
    user: str = "1",
    parent: str | None = None,
    args: dict[str, Any] | None = None,
    app: str = "testapp",
    action: str = "actionhash",
) -> str:
    """Build a base64url-encoded Rekuest-Task header payload."""
    payload = {
        "id": task_id,
        "parent": parent,
        "args": args if args is not None else {"x": 1},
        "user": user,
        "app": app,
        "action": action,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Headers for the static "test" token (sub "1", org "static_org")."""
    return {"Authorization": "Bearer test"}


@pytest.fixture
def task_headers(auth_headers) -> dict[str, str]:
    """Auth headers plus a Rekuest task assigned by the requesting user."""
    return {**auth_headers, "Rekuest-Task": task_header()}
