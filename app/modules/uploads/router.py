from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/images")
def upload_multiple_images(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    uploaded_images = []

    for file in files:
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} is not allowed. Only jpg, jpeg, png, and webp images are allowed",
            )

        filename = f"{uuid4().hex}{file_ext}"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as buffer:
            buffer.write(file.file.read())

        uploaded_images.append({
            "original_name": file.filename,
            "image_url": f"/static/uploads/{filename}",
        })

    return {
        "count": len(uploaded_images),
        "images": uploaded_images,
    }