"""Run the AURORA API with uvicorn: ``python -m aurora.app.api``."""

from __future__ import annotations

import os

from aurora.app.api.app import create_app

app = create_app(
    workspace_root=os.getcwd(),
    frontend_dir=os.environ.get("AURORA_FRONTEND_DIR"),
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
