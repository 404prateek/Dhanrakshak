import os
import logging
from fastapi import UploadFile, HTTPException
from app.storage.local_storage import local_storage
from sqlalchemy.orm import Session
from app.models.case import Document

logger = logging.getLogger(__name__)


class FileManager:
    @staticmethod
    async def process_and_save_upload(
        db: Session,
        file: UploadFile,
        case_id: int,
        uploader_id: int | None = None,  # nullable — hardcoded admin has no DB row
    ) -> Document:
        try:
            subfolder = f"case_{case_id}"
            saved_path = await local_storage.save_file(file, subfolder=subfolder)

            doc = Document(
                case_id=case_id,
                file_name=file.filename,
                file_type=file.content_type or "application/octet-stream",
                file_path=saved_path,
                uploaded_by=None,   # FK omitted — no real user row in DB
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            logger.info("Document saved: %s (case %s)", file.filename, case_id)
            return doc
        except Exception as exc:
            db.rollback()
            logger.error("Upload failed for case %s: %s", case_id, exc, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc

