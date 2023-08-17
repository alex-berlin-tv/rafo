from .config import settings
from .omnia import Omnia, StreamType

import typer
import uvicorn


app = typer.Typer()


@app.command()
def run():
    """Starts the web-server."""
    uvicorn.run(
        "rafo.server:app",
        reload=settings.dev_mode,
        port=settings.port,
        proxy_headers=True,
        log_level=settings.log_level,
    )


@app.command()
def test():
    omnia = Omnia.from_config()
    result = omnia.upload_by_url(
        StreamType.AUDIO_STREAM_TYPE,
        "https://db.alex-berlin.de/download//o5jmhoqWKTJQOz1kuj.mp3",
        True
    )
    print(result)



if __name__ == "__main__":
    app()