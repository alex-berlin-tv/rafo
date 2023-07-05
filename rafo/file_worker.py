from config import settings
from model import get_nocodb_client, get_nocodb_project
from noco_upload import Upload

from pathlib import Path
import time


class FileWorker:
    def __init__(self, path: Path, episode_id: int):
        self.path = path
        self.episode_id = episode_id
    
    def upload_raw(self):
        upload = Upload(
            settings.nocodb_url, # type: ignore
            settings.nocodb_api_key, # type: ignore
            get_nocodb_client(),
            get_nocodb_project(settings.project_name),
        )
        upload.upload_file(
            self.path,
            settings.episode_table, # type: ignore
            settings.raw_column, # type: ignore
            self.episode_id,
        )
    
    def generate_waveform(self):
        time.sleep(5)
    
    def optimize_file(self):
        time.sleep(5)