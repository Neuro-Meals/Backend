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

    # All users are protected by an IP-based rate limit.
    rate_limit(
        key=f"rate:chatbot:ip:{ip_address}",
        limit=30,
        window_seconds=600,
    )

    if current_user:
        # Logged-in users receive a higher limit and personalized context.
        rate_limit(
            key=f"rate:chatbot:user:{current_user.id}",
            limit=20,
            window_seconds=600,
        )
    else:
        # Anonymous visitors receive a lower allowance.
        rate_limit(
            key=f"rate:chatbot:anonymous:{ip_address}",
            limit=10,
            window_seconds=600,
        )

    try:
        answer = generate_chatbot_answer(
            db=db,
            user=current_user,
            message=payload.message.strip(),
            history=payload.history,
        )

    except RuntimeError as exc:
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