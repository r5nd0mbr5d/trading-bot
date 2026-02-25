"""Run read-only dashboard API server."""

from src.api.app import create_app


def main() -> None:
    """Entrypoint for uvicorn-based API server."""
    import uvicorn

    app = create_app("trading_paper.db")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
