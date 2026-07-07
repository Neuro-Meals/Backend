from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@router.post("/image")
def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
        )
    ),
):
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only jpg, jpeg, png, and webp images are allowed",
        )

    filename = f"{uuid4().hex}{file_ext}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    return {
        "image_url": f"/static/uploads/{filename}"
    }