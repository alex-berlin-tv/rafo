from config import settings
from model import get_nocodb_client, get_nocodb_project
from noco_upload import Upload

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
            settings.nocodb_url,  # type: ignore
            settings.nocodb_api_key,  # type: ignore
            get_nocodb_client(),
            get_nocodb_project(settings.project_name),
        )

    def upload_raw(self):
        self.upload.upload_file(
            self.raw_file,
            settings.episode_table,  # type: ignore
            settings.raw_column,  # type: ignore
            self.episode_id,
        )
        with self.count_lock:
            self.finished_workers += 1

    def generate_waveform(
        self,
        gain: int = 0,
        width: int = 600,
        height: int = 252,
        color: str = "#3399cc"
    ):
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
            settings.episode_table, # type: ignore
            settings.waveform_column, # type: ignore
            self.episode_id,
        )
        with self.count_lock:
            self.finished_workers += 1

    def optimize_file(self):
        with self.count_lock:
            self.finished_workers += 1

    def delete_temp_folder_on_completion(self):
        while self.finished_workers != 3:
            pass
        shutil.rmtree(self.temp_folder)
