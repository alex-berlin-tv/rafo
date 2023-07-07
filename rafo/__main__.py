from config import settings
from model import get_nocodb_data

import click
import requests
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
    url = "https://db.alex-berlin.de/api/v1/db/data/noco/p_pukky1xtpbvkl8/Episoden"
    querystring = {"offset":"0","limit":"25","where":""}
    headers = {"xc-auth": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6Im9ubGluZUBhbGV4LWJlcmxpbi5kZSIsImZpcnN0bmFtZSI6bnVsbCwibGFzdG5hbWUiOm51bGwsImlkIjoidXNfYmttcXo4NHp3ZjQ3dXgiLCJyb2xlcyI6Im9yZy1sZXZlbC1jcmVhdG9yLHN1cGVyIiwidG9rZW5fdmVyc2lvbiI6IjdjNjE5Njg5MTdhOTZiZDkyODViMDAyZjQwMDBmODAwNWFlOTliYjBmOTZlZDk2NTk3ZGI2YTA5Mjc2MWVmMWVjYjhkMmE4NDA0ZTIzMjM0IiwiaWF0IjoxNjg4NzI5NTcyLCJleHAiOjE2ODg3NjU1NzJ9.htrvX7L4hUAHPqaiFpbhdTO6giGBPjb0Vlj1e6c4Bi4"}
    response = requests.request("GET", url, headers=headers, params=querystring)
    print(response.text)


if __name__ == "__main__":
    cli.add_command(run)
    cli.add_command(test)
    cli()