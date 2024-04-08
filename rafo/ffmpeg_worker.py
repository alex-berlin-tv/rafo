from pathlib import Path
import re
import subprocess
from typing import Optional

import ffmpeg

from rafo.config import settings
from rafo.log import logger
from rafo.model import BaserowPerson, BaserowShow, BaserowUpload


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
        logger.debug(f"About to run ffprobe for {input_file}")
        self.data = ffmpeg.probe(input_file)

    def duration(self) -> float:
        """Duration of the media file in seconds."""
        return float(self.data["streams"][0]["duration"])

    def formatted_duration(self) -> str:
        """Human readable duration in the HH:MM.ss format."""
        seconds = self.duration()
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


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

    silence_start_re = re.compile(
        r" silence_start: (?P<start>[0-9]+(\.?[0-9]*)).*$")
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
        if self.whole_file_is_silence():
            return f"- Whole file appears to be silence"
        if start_silence:
            rsl.append(
                f"- Silence found and removed at the start ({start_silence.start:.2f})")
        end_silence = self.end_silence()
        if end_silence:
            rsl.append(
                f"- Silence found and removed at the end ({end_silence.end:.2f})")
        for silence in self.intermediate_silences():
            rsl.append(
                f"- Intermediate silence found, this has to be resolved manually ({silence.start:.2f} to {silence.end:.2f}) ")
        return "\n".join(rsl)

    @staticmethod
    def __run_silence_detection(input_file: Path) -> list[str]:
        logger.debug("About to run ffmpeg with silencedetect")
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


class Optimize:
    """
    Tries to automatically optimize an audio file. It does the following:

    - Crop silence at the start of the file.
    - Crop silence at the end of the file.
    - Applies the default bit and sample rate (taken from the config file).
    - Converts the file to mp3
    - Writes the filename as title into the metadata (this is needed as otherwise
    mAirList cannot read the file.)
    - Applies the EBU loudness-norm
    """

    def __init__(
        self,
        input_file: Path,
        silence: Silence,
        upload: BaserowUpload,
        person: BaserowPerson,
        show: BaserowShow,
    ):
        self.__input_file = input_file
        self.__silence = silence
        self.__upload = upload
        self.__person = person
        self.__show = show

    def run(self, output_file: Path):
        """ Applies the optimization."""
        input_options = {}
        start_silence = self.__silence.start_silence()
        if start_silence and start_silence.end > settings.audio_crop_allowance:
            logger.info(
                f"Found silence at the start with a duration of {start_silence.duration:.2f}, will crop")
            input_options["ss"] = start_silence.end - \
                settings.audio_crop_allowance
        end_silence = self.__silence.end_silence()
        if end_silence:
            logger.info(
                f"Found silence at the end with a duration of {end_silence.duration:.2f}, will crop")
            input_options["to"] = end_silence.start + \
                settings.audio_crop_allowance

        date = self.__upload.planned_broadcast_at.strftime("%d.%m.%Y %H:%M")
        ffmpeg.input(
            str(self.__input_file),
            **input_options
        ).audio.filter(
            "loudnorm"
        ).output(
            str(output_file),
            audio_bitrate=settings.bit_rate,
            ar=settings.sample_rate,
            **{
                "metadata:g:0": f"title={output_file.stem}",
                "metadata:g:1": f"artist={self.__person.name} (p-{self.__person.row_id:03})",
                "metadata:g:2": f"album={self.__show.name} (s-{self.__show.row_id:03})",
                "metadata:g:3": f"track=Upload entry: {self.__upload.row_id}",
                "metadata:g:4": f"date={date}",
            }
        ).run()
