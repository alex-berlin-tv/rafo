from .config import settings
from .log import logger

from pathlib import Path
import re
import subprocess
from typing import Optional

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


class SilencePart:
    """States the position and duration of silence."""

    def __init__(self, start: float, end: float, duration: float):
        self.start = start
        self.end = end
        self.duration = duration

    def is_at_start(self) -> bool:
        """Checks whether the silence is at the start of the file."""
        return self.start == 0.0

    def is_at_end(self, file_duration: float) -> bool:
        """Checks whether the silence is at the start of the file."""
        delta = abs(round(file_duration) - round(self.end))
        return delta < 2

    def is_whole_file(self, file_duration) -> bool:
        """Checks whether duration equals to the whole file."""
        delta = abs(round(file_duration) - round(self.duration))
        return delta < 2


class SilenceParts:
    silence_start_re = re.compile(r" silence_start: (?P<start>[0-9]+(\.?[0-9]*)).*$")
    silence_end_re = re.compile(r" silence_end: (?P<end>[0-9]+(\.?[0-9]*))")

    def __init__(self, root: list[SilencePart]):
        self.root = root

    @classmethod
    def from_ffmpeg_output(cls, lines: list[str]):
        silence_index = -1
        rsl: list[SilencePart] = []
        for line in lines:
            start_entry_match = SilenceParts.silence_start_re.search(line)
            if start_entry_match:
                start = float(start_entry_match.group("start"))
                silence_index += 1
                rsl.append(SilencePart(start, -1, -1))
            end_entry_match = SilenceParts.silence_end_re.search(line)
            if end_entry_match:
                end = float(end_entry_match.group("end"))
                rsl[silence_index].end = end
                rsl[silence_index].duration = end - rsl[silence_index].start
        return cls(rsl)


class Silence:
    """Detect silence."""

    def run(self, input_file: Path) -> SilenceParts:
        popen = subprocess.Popen(
            (ffmpeg
                .input(str(input_file))
                .audio.filter(
                    "silencedetect", noise=settings.noise_tolerance, duration=settings.silence_duration
                )
                .output("-", format="null")
                .compile()
            ),
            stderr=subprocess.PIPE,
        )
        output = popen.communicate()[1].decode().splitlines()
        return SilenceParts.from_ffmpeg_output(output)
