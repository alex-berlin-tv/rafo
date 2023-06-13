from config import settings
from model import get_nocodb_data

import click
import uvicorn

@click.group()
def cli():
    pass


@click.command()
def run():
    """Starts the web-server."""
    uvicorn.run("server:app", reload=True, port=settings.port) # type: ignore


@click.command()
def test():
    data = get_nocodb_data(settings.project_name, settings.episode_table) # type: ignore
    print(data)


if __name__ == "__main__":
    cli.add_command(run)
    cli.add_command(test)
    cli()