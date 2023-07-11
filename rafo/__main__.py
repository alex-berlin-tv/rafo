from .config import settings
from .model import NocoEpisode

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
        reload=True,
        port=settings.port, # type: ignore
        proxy_headers=True # type: ignore
    )


@click.command()
def test():
    episode = NocoEpisode.from_nocodb_by_uuid("fd1c1b27-4d1f-4f92-8e4a-d87b5b7f907b")


def main():
    cli.add_command(run)
    cli.add_command(test)
    cli()


if __name__ == "__main__":
    main()