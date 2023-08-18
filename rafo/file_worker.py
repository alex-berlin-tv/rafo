from .config import settings
from .ffmpeg import Metadata, Optimize, Silence, Waveform
from .log import logger
from .model import get_nocodb_client, get_nocodb_project, NocoEpisode, OptimizingState, WaveformState
from .noco_upload import Upload

from pathlib import Path
import shutil
import threading
from typing import Optional


class FileWorker:
    def __init__(self, raw_file: Path, cover_file: Optional[Path], temp_folder: Path, episode_id: int):
        self.raw_file = raw_file
        self.cover_file = cover_file
        self.temp_folder = temp_folder
        self.episode_id = episode_id
        self.count_lock = threading.Lock()
        self.finished_workers = 0
        self.upload = Upload(
            settings.nocodb_url,
            settings.nocodb_api_key, 
            get_nocodb_client(),
            get_nocodb_project(),
        )
        self.__cached_episode: Optional[NocoEpisode] = None
        self.__file_name_prefix: Optional[str] = None

    def upload_raw(self):
        logger.debug(f"About to upload raw file {self.raw_file}")
        self.__upload_named_file(self.raw_file, "raw", "Quelldatei")
        with self.count_lock:
            self.finished_workers += 1
        
    def upload_cover(self):
        if self.cover_file is None:
            logger.debug("No cover file available to be uploaded")
            return
        self.__upload_named_file(self.cover_file, "cover", "Cover")
        with self.count_lock:
            self.finished_workers += 1

    def generate_waveform(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
        self.__episode().update_state_waveform(WaveformState.RUNNING)
        waveform = Waveform(gain, width, height, color)
        file_name = self.__file_name("waveform-raw", ".png")
        output_path = self.temp_folder / file_name
        try:
            err = waveform.run(
                self.raw_file,
                output_path, 
            )
            self.upload.upload_file(
                output_path,
                file_name,
                settings.episode_table,
                settings.waveform_column,
                self.episode_id,
            )
        except Exception:
            with self.count_lock:
                self.finished_workers += 1
            self.__episode().update_state_waveform(WaveformState.ERROR)
            raise
        if err is not None:
            self.__episode().update_state_waveform(WaveformState.ERROR)
        else:
            self.__episode().update_state_waveform(WaveformState.DONE)
        logger.info(f"Waveform generated for {self.raw_file} and written to {output_path}")
        with self.count_lock:
            self.finished_workers += 1

    def optimize_file(self):
        self.__episode().update_state_optimizing(OptimizingState.RUNNING)
        file_name = self.__file_name("opt", ".mp3")
        output_path = self.temp_folder / file_name
        try:
            silence = Silence(self.raw_file)
            optimize = Optimize(self.raw_file, silence)
            optimize.run(output_path)
            duration = Metadata(output_path).formatted_duration()

            log = silence.log()
            if log == "":
                self.__episode().update_state_optimizing(OptimizingState.DONE)
            else:
                self.__episode().update_state_optimizing(OptimizingState.SEE_LOG)

            log = f"{log}\nFinal running time: {duration}"
            self.__episode().update_optimizing_log(log) 

            self.__upload_named_file(output_path, "opt", "Optimierte Datei")

        except Exception:
            self.__episode().update_state_optimizing(OptimizingState.ERROR)
            with self.count_lock:
                self.finished_workers += 1

        with self.count_lock:
            self.finished_workers += 1

    def delete_temp_folder_on_completion(self):
        while self.finished_workers != 4:
            pass
        logger.debug(f"Delete temp folder {self.temp_folder}")
        shutil.rmtree(self.temp_folder)
    
    def __upload_named_file(
        self,
        file: Path,
        name: str,
        column_id: str,
    ):
        """Upload files with the required name-schema from the temp folder."""

        logger.debug(f"About to upload {name} file {self.cover_file}")
        named_file = file.with_name(self.__file_name(name, None)).with_suffix(file.suffix)
        shutil.copy(file, named_file)
        self.upload.upload_file(
            named_file,
            self.__file_name(name, self.raw_file.suffix),
            settings.episode_table,
            column_id,
            self.episode_id,
        )
        logger.info(f"{name.title()} file {self.cover_file} uploaded to NocoDB")
    
    def __episode(self) -> NocoEpisode:
        """Provides the (cached) Episode."""
        if self.__cached_episode is None:
            self.__cached_episode = NocoEpisode.from_nocodb_by_id(self.episode_id)
        return self.__cached_episode
    
    def __file_name(self, slug: str, extension: Optional[str]) -> str:
        """
        Cached method for getting a file name. Has to be cached as multiple methods
        of the file worker need a file name but getting it needs at least two API
        calls.
        
        If `extension` is `None` the method will not append any file extension.
        """
        if extension is None:
            extension = ""
        elif extension[0] != ".":
            extension = f".{extension}"
        if self.__file_name_prefix is None:
            self.__file_name_prefix = self.__episode().file_name_prefix()
        return f"{self.__file_name_prefix}_{slug}{extension}"