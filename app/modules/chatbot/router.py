from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.core.rate_limiter import (
    get_client_ip,
    rate_limit,
)
from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_optional_current_user,
)
from app.modules.chatbot.schemas import (
    ChatRequest,
    ChatResponse,
)
from app.modules.chatbot.service import (
    generate_chatbot_answer,
)
from app.modules.users.models import User


router = APIRouter(
    prefix="/chatbot",
    tags=["AI Chatbot"],
)


@router.post(
    "/ask",
    response_model=ChatResponse,
)
def ask_chatbot(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(
        get_optional_current_user
    ),
):
    ip_address = get_client_ip(request)

    # General protection applying to every request.
    rate_limit(
        key=f"rate:chatbot:ip:{ip_address}",
        limit=30,
        window_seconds=600,
    )

    if current_user is not None:
        # Logged-in users:
        # maximum 20 messages every 10 minutes per account.
        rate_limit(
            key=f"rate:chatbot:user:{current_user.id}",
            limit=20,
            window_seconds=600,
        )
    else:
        # Anonymous visitors:
        # maximum 10 messages every 10 minutes per IP.
        rate_limit(
            key=f"rate:chatbot:anonymous:{ip_address}",
            limit=10,
            window_seconds=600,
        )

    try:
        answer = generate_chatbot_answer(
            db=db,
            user=current_user,
            message=payload.message,
            history=payload.history,

            # For a logged-in user, the service uses user.id.
            # For an anonymous visitor, it hashes this identifier.
            anonymous_identifier=ip_address,
        )

    except RuntimeError as exc:
        # Log the original error internally.
        # Do not expose API or provider details to the frontend.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI assistant is temporarily unavailable",
        ) from exc

    return ChatResponse(
        answer=answer,
        model="NutrioMeals AI",
        scope="nutriomeals",
        authenticated=current_user is not None,
    )