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
from app.modules.auth.dependencies import get_current_user
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
    current_user: User = Depends(get_current_user),
):
    ip_address = get_client_ip(request)

    # Per-user protection:
    # maximum 20 chatbot messages every 10 minutes.
    rate_limit(
        key=f"rate:chatbot:user:{current_user.id}",
        limit=20,
        window_seconds=600,
    )

    # Extra IP protection:
    # maximum 50 messages every 10 minutes from one IP.
    rate_limit(
        key=f"rate:chatbot:ip:{ip_address}",
        limit=50,
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
        # Log the original exception internally in production.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI assistant is temporarily unavailable",
        ) from exc

    return ChatResponse(
        answer=answer,
        model="NutrioMeals AI",
        scope="nutriomeals",
    )