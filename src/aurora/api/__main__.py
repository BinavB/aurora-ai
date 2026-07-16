"""Run the AURORA API with uvicorn: ``python -m aurora.api``."""

from __future__ import annotations

import os

from aurora.api.app import create_app
from aurora.memory import build_memory_from_env
from aurora.tools.registry import default_registry

app = create_app(
    memory=build_memory_from_env(),
    tools=default_registry(os.getcwd()),
)


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("AURORA_HOST", "127.0.0.1"),
        port=int(os.environ.get("AURORA_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
