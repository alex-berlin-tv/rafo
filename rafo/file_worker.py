from os import execlp
from .config import settings
from .log import logger
from .model import get_nocodb_client, get_nocodb_project
from .noco_upload import Upload

from pathlib import Path
import shutil
import threading
import time

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

    def upload_raw(self):
        logger.debug(f"About to upload raw file {self.raw_file}")
        self.upload.upload_file(
            self.raw_file,
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
        try:
            output_path = self.temp_folder / Path("raw_waveform.png")
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
