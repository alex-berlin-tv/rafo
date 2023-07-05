from config import settings
from file_worker import FileWorker

from pathlib import Path

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
    # data = get_nocodb_data(settings.project_name, settings.episode_table) # type: ignore
    # print(data)
    worker = FileWorker(Path("/Users/irvin/repos/audiocat-old/test_upload/s-0002_e-000007_raw.mp3"), 4)
    worker.upload_raw()


if __name__ == "__main__":
    cli.add_command(run)
    cli.add_command(test)
    cli()