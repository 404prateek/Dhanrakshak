import os
import shutil
from fastapi import UploadFile
from app.core.config import settings

class LocalStorage:
    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = base_dir  # Keep it as ./storage/uploads for DB/frontend consistency
        
        # Calculate the absolute directory for internal OS operations
        if not os.path.isabs(self.base_dir):
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self._abs_dir = os.path.abspath(os.path.join(backend_dir, self.base_dir))
        else:
            self._abs_dir = os.path.abspath(self.base_dir)
            
        os.makedirs(self._abs_dir, exist_ok=True)
        
    async def save_file(self, file: UploadFile, subfolder: str = "") -> str:
        target_dir = os.path.join(self._abs_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)
        
        abs_file_path = os.path.join(target_dir, file.filename)
        
        with open(abs_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return the relative path so the frontend getDocumentUrl logic works
        relative_path = os.path.join(self.base_dir, subfolder, file.filename).replace("\\", "/")
        return relative_path
    
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
