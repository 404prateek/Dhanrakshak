import os
import shutil
from fastapi import UploadFile
from app.core.config import settings

class LocalStorage:
    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    async def save_file(self, file: UploadFile, subfolder: str = "") -> str:
        target_dir = os.path.join(self.base_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)
        
        file_path = os.path.join(target_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return file_path
    
    def get_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError("File not found")
        return file_path
    
    def delete_file(self, file_path: str) -> bool:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

local_storage = LocalStorage()
