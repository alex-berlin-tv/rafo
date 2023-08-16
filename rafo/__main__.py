from .config import settings
from .ffmpeg import Silence, Metadata

from pathlib import Path

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
def test(path: Path):
    silence = Silence(path)

    print(f"Start {silence.start_silence()}")
    
    for part in silence.intermediate_silences():
        print(f"Intermediate {part}")
    print(f"End {silence.end_silence()}")
    print(f"Whole {silence.whole_file_is_silence()}")


if __name__ == "__main__":
    app()