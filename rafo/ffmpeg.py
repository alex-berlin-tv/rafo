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


class Metadata:
    """Get metadata."""

    def __init__(self, input_file: Path):
        self.data = ffmpeg.probe(input_file)

    def duration(self) -> float:
        return float(self.data["streams"][0]["duration"])


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

    def __str__(self) -> str:
        return f"start: {self.start}, end: {self.end}, duration: {self.duration}"


class Silence:
    """Detect silence."""

    silence_start_re = re.compile(r" silence_start: (?P<start>[0-9]+(\.?[0-9]*)).*$")
    silence_end_re = re.compile(r" silence_end: (?P<end>[0-9]+(\.?[0-9]*))")

    def __init__(self, input_file: Path):
        output = self.__run_silence_detection(input_file)
        self.__silence_parts = self.__parse_ffmpeg_output(output)
        self.__metadata = Metadata(input_file)

    def start_silence(self) -> Optional[SilencePart]:
        """Returns a `SilencePart` if there is one at the start of the file."""
        for silence_part in self.__silence_parts:
            if silence_part.is_at_start():
                return silence_part
        return None
    
    def intermediate_silences(self) -> list[SilencePart]:
        """Returns a list of all `SilencePart`s which are not at the start or end of the file."""
        rsl: list[SilencePart] = []
        for silence_part in self.__silence_parts:
            if silence_part.is_at_start():
                continue
            if silence_part.is_at_end(self.__metadata.duration()):
                continue
            rsl.append(silence_part)
        return rsl
    
    def end_silence(self) -> Optional[SilencePart]:
        """Returns a `SilencePart` if there is one at the end of the file."""
        for silence_part in self.__silence_parts:
            if silence_part.is_at_end(self.__metadata.duration()):
                return silence_part
        return None
    
    def whole_file_is_silence(self) -> bool:
        """Returns whether whole file is silence."""
        for silence_part in self.__silence_parts:
            if silence_part.is_whole_file(self.__metadata.duration()):
                return True
        return False
    
    def log(self) -> str:
        """
        Human readable log of all silence in the file appended to NocoDB to be viewed by the user.
        """
        rsl: list[str] = []
        start_silence = self.start_silence()
        if start_silence:
            rsl.append(f"- Silence found and removed at the start ({start_silence})")
        end_silence = self.end_silence()
        if end_silence:
            rsl.append(f"- Silence found and removed at the end ({end_silence})")
        for silence in self.intermediate_silences():
            rsl.append(f"- Intermediate silence found, this has to be resolved manually ({silence}) ")
        if self.whole_file_is_silence():
            rsl.append(f"- Whole file appears to be silence")
        return "\n".join(rsl)
        

    @staticmethod
    def __run_silence_detection(input_file: Path) -> list[str]:
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
        return popen.communicate()[1].decode().splitlines()
    
    @staticmethod
    def __parse_ffmpeg_output(ffmpeg_output: list[str]) -> list[SilencePart]:
        silence_index = -1
        rsl: list[SilencePart] = []
        for line in ffmpeg_output:
            start_entry_match = Silence.silence_start_re.search(line)
            if start_entry_match:
                start = float(start_entry_match.group("start"))
                silence_index += 1
                rsl.append(SilencePart(start, -1, -1))
            end_entry_match = Silence.silence_end_re.search(line)
            if end_entry_match:
                end = float(end_entry_match.group("end"))
                rsl[silence_index].end = end
                rsl[silence_index].duration = end - rsl[silence_index].start
        return rsl
