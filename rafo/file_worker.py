from os import execlp
from typing import Optional
from .config import settings
from .log import logger
from .model import get_nocodb_client, get_nocodb_project, NocoEpisode
from .noco_upload import Upload

from pathlib import Path
import shutil
import threading

import ffmpeg


class FileWorker:
    def __init__(self, raw_file: Path, temp_folder: Path, episode_id: int):
        self.raw_file = raw_file
        self.temp_folder = temp_folder
        self.episode_id = episode_id
        self.count_lock = threading.Lock()
        self.finished_workers = 0
        self.upload = Upload(
            settings.nocodb_url,
            settings.nocodb_api_key, 
            get_nocodb_client(),
            get_nocodb_project(settings.project_name),
        )
        self.file_name_prefix: Optional[str] = None

    def upload_raw(self):
        logger.debug(f"About to upload raw file {self.raw_file}")
        named_file = self.raw_file.with_name(self.__file_name("raw", None)).with_suffix(self.raw_file.suffix)
        shutil.copy(self.raw_file, named_file)
        logger.warning(named_file)
        self.upload.upload_file(
            named_file,
            self.__file_name("raw", self.raw_file.suffix),
            settings.episode_table, 
            settings.raw_column, 
            self.episode_id,
        )
        logger.info(f"Raw file {self.raw_file} uploaded to NocoDB")
        with self.count_lock:
            self.finished_workers += 1

    def generate_waveform(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
        logger.debug(f"About to generate waveform for {self.raw_file}")
        file_name = self.__file_name("waveform-raw", ".png")
        try:
            output_path = self.temp_folder / Path(file_name)
            out, err = ffmpeg.input(
                str(self.raw_file)
            ).filter(
                "aformat", channel_layouts="mono",
            ).filter(
                "compand", gain=gain,
            ).filter(
                "showwavespic", s=f"{width}x{height}", colors=color,
            ).output(
                str(output_path), vframes=1,
            ).overwrite_output().run()
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
            raise
        logger.info(f"Waveform generated for {self.raw_file} and written to {output_path}")
        with self.count_lock:
            self.finished_workers += 1

    def optimize_file(self):
        with self.count_lock:
            self.finished_workers += 1

    def delete_temp_folder_on_completion(self):
        while self.finished_workers != 3:
            pass
        logger.debug(f"Delete temp folder {self.temp_folder}")
        shutil.rmtree(self.temp_folder)
    
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
        if self.file_name_prefix is None:
            episode = NocoEpisode.from_nocodb_by_id(self.episode_id)
            self.file_name_prefix = episode.file_name_prefix()
        return f"{self.file_name_prefix}_{slug}{extension}"