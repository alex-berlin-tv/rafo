import argparse

import uvicorn

from rafo.config import settings


def run():
    """Starts the web-server."""
    uvicorn.run(
        "rafo.server:app",
        reload=settings.dev_mode,
        port=settings.port,
        proxy_headers=True,
        log_level=settings.log_level,
    )


def app():
    parser = argparse.ArgumentParser(
        description="The (radio) upload form for ALEX Berlin",
    )
    sub_parsers = parser.add_subparsers(
        dest="command", help="Available commands")
    run_parser = sub_parsers.add_parser("run", help="Starts the web-server.")
    run_parser.set_defaults(func=run)
    args = parser.parse_args()
    if args.command:
        args.func()
    else:
        parser.print_help()


if __name__ == "__main__":
    app()
