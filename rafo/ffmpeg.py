from typing import Optional
from .log import logger

from pathlib import Path

import ffmpeg


class Waveform:
    """Generate waveforms."""

    def __init__(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
        self.gain = gain
        self.width = width
        self.height = height
        self.color = color
    
    def run(self, input_file: Path, output_file: Path) -> Optional[ffmpeg.Error]:
        logger.debug(f"About to generate waveform for {input_file}")
        _, err = ffmpeg.input(
            str(input_file)
        ).filter(
            "aformat", channel_layouts="mono",
        ).filter(
            "compand", gain=self.gain,
        ).filter(
            "showwavespic", s=f"{self.width}x{self.height}", colors=self.color,
        ).output(
            str(output_file), vframes=1,
        ).overwrite_output().run()
        return err
