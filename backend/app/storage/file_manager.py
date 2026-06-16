from fastapi import UploadFile
from app.storage.local_storage import local_storage
from sqlalchemy.orm import Session
from app.models.case import Document
import os

class FileManager:
    @staticmethod
    async def process_and_save_upload(db: Session, file: UploadFile, case_id: int, uploader_id: int) -> Document:
        # Save file to local storage
        subfolder = f"case_{case_id}"
        saved_path = await local_storage.save_file(file, subfolder=subfolder)
        
        # Create database record
        doc = Document(
            case_id=case_id,
            file_name=file.filename,
            file_type=file.content_type or "application/octet-stream",
            file_path=saved_path,
            uploaded_by=uploader_id
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc
