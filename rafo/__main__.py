from config import settings

import click
import uvicorn

@click.group()
def cli():
    pass


@click.command()
def run():
    """Starts the web-server."""
    uvicorn.run("server:app", reload=True, port=settings.port) # type: ignore


if __name__ == "__main__":
    cli.add_command(run)
    cli()