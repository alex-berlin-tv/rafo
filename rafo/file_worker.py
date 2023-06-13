from pathlib import Path
import time


class FileWorker:
    def __init__(self, path: Path):
        self.path = path
    
    def upload_raw(self):
        time.sleep(5)
    
    def generate_waveform(self):
        time.sleep(5)
    
    def optimize_file(self):
        time.sleep(5)
    