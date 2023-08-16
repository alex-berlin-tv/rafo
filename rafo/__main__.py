from .config import settings
from .ffmpeg import Silence

from pathlib import Path

import click
import uvicorn

@click.group()
def cli():
    pass


@click.command()
def run():
    """Starts the web-server."""
    uvicorn.run(
        "rafo.server:app",
        reload=settings.dev_mode,
        port=settings.port,
        proxy_headers=True,
        log_level=settings.log_level,
    )


@click.command()
def test():
    silence = Silence()
    parts = silence.run(Path("misc/optimize_test.wav"))
    for part in parts.root:
        print(f"{part.start}, {part.end}, {part.duration}")


def main():
    cli.add_command(run)
    cli.add_command(test)
    cli()


if __name__ == "__main__":
    main()