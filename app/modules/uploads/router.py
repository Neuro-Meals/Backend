from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image

from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/uploads", tags=["Uploads"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

@router.post("/images")
async def upload_multiple_images(
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
        extension = Path(file.filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{file.filename} is not allowed. "
                    "Only JPG, JPEG, PNG and WEBP images are supported."
                ),
            )

        contents = await file.read()

        if len(contents) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{file.filename} exceeds the maximum "
                    "allowed size of 5 MB."
                ),
            )

        try:
            Image.open(file.file)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} is not a valid image.",
            )

        await file.seek(0)

        filename = f"{uuid4().hex}{extension}"
        filepath = UPLOAD_DIR / filename

        with open(filepath, "wb") as buffer:
            buffer.write(contents)

        uploaded_images.append(
            {
                "original_name": file.filename,
                "image_url": f"/static/uploads/{filename}",
            }
        )

    return {
        "count": len(uploaded_images),
        "images": uploaded_images,
    }