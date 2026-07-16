from datetime import date, timedelta

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    require_roles,
)
from app.modules.orders.automation_schemas import (
    AutomaticOrderGenerationResponse,
)
from app.modules.orders.automation_service import (
    WEEKDAY_MAPPING,
    build_subscription_order_items,
    confirm_scheduled_orders_for_date,
    generate_orders_for_date,
    subscription_is_valid_for_date,
)
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import User, UserRole


router = APIRouter(
    prefix="/orders/automation",
    tags=["Automatic Orders"],
)


@router.post(
    "/generate",
    response_model=AutomaticOrderGenerationResponse,
)
def generate_automatic_orders(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    return generate_orders_for_date(
        db=db,
        target_date=target_date,
    )


@router.post(
    "/generate-tomorrow",
    response_model=AutomaticOrderGenerationResponse,
)
def generate_tomorrow_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    tomorrow = date.today() + timedelta(
        days=1
    )

    return generate_orders_for_date(
        db=db,
        target_date=tomorrow,
    )
    
    
@router.post(
    "/confirm-today",
)
def confirm_today_scheduled_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    return confirm_scheduled_orders_for_date(
        db=db,
        target_date=date.today(),
    )    


@router.get(
    "/preview",
)
def preview_automatic_orders(
    target_date: date = Query(
        default_factory=date.today,
        alias="date",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.CHEF,
        )
    ),
):
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.status
            == SubscriptionStatus.ACTIVE,
            Subscription.payment_status
            == PaymentStatus.PAID,
        )
        .order_by(Subscription.id.asc())
        .all()
    )

    data = []

    for subscription in subscriptions:
        if not subscription_is_valid_for_date(
            subscription,
            target_date,
        ):
            continue

        items = build_subscription_order_items(
            db=db,
            subscription=subscription,
            target_date=target_date,
        )

        user = (
            db.query(User)
            .filter(
                User.id
                == subscription.user_id
            )
            .first()
        )

        plan = (
            db.query(MealPlan)
            .filter(
                MealPlan.id
                == subscription.plan_id
            )
            .first()
        )

        data.append(
            {
                "subscription_id": (
                    subscription.id
                ),
                "user_id": subscription.user_id,
                "customer": (
                    {
                        "id": user.id,
                        "name": (
                            f"{user.first_name} "
                            f"{user.last_name}"
                        ).strip(),
                        "phone": user.phone,
                        "address": user.address,
                        "allergies": (
                            user.allergies or []
                        ),
                    }
                    if user
                    else None
                ),
                "plan": (
                    {
                        "id": plan.id,
                        "name": plan.name_en,
                    }
                    if plan
                    else None
                ),
                "meal_count": len(items),
                "items": items,
            }
        )

    return {
        "target_date": target_date,
        "weekday": WEEKDAY_MAPPING[
            target_date.weekday()
        ].value,
        "total_subscriptions": len(data),
        "data": data,
    }