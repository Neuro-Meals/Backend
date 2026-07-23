from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import (
    get_current_user,
    require_roles,
)
from app.modules.meals.models import MealCategory
from app.modules.orders.models import Order
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import (
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import (
    User,
    UserCategoryDeliveryPreference,
    UserRole,
)
from app.modules.users.schemas import (
    CompleteProfileUpdate,
    UserResponse,
    UserUpdate,
    UserUpdateRole,
)
from app.modules.users.service import (
    get_user_by_id,
    normalize_phone,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


def enum_value(value):
    """
    Convert an enum to its string value.
    """
    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return value


def clean_optional_text(value: str | None) -> str | None:
    """
    Remove unnecessary spaces from optional text values.
    """
    if value is None:
        return None

    cleaned_value = value.strip()

    if not cleaned_value:
        return None

    return cleaned_value


def build_subscription_data(
    db: Session,
    user_id: int,
) -> dict | None:
    """
    Return the user's active subscription.

    If the user has no active subscription, return
    their most recent subscription.
    """

    active_subscription = (
        db.query(
            Subscription,
            MealPlan,
        )
        .join(
            MealPlan,
            Subscription.plan_id == MealPlan.id,
        )
        .filter(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .order_by(
            Subscription.id.desc(),
        )
        .first()
    )

    subscription_row = active_subscription

    if subscription_row is None:
        subscription_row = (
            db.query(
                Subscription,
                MealPlan,
            )
            .join(
                MealPlan,
                Subscription.plan_id == MealPlan.id,
            )
            .filter(
                Subscription.user_id == user_id,
            )
            .order_by(
                Subscription.id.desc(),
            )
            .first()
        )

    if subscription_row is None:
        return None

    subscription, plan = subscription_row

    return {
        "id": subscription.id,
        "plan_id": subscription.plan_id,
        "status": enum_value(subscription.status),
        "payment_status": enum_value(
            subscription.payment_status
        ),
        "amount": (
            float(subscription.amount)
            if subscription.amount is not None
            else 0.0
        ),
        "start_date": (
            subscription.start_date.isoformat()
            if subscription.start_date
            else None
        ),
        "end_date": (
            subscription.end_date.isoformat()
            if subscription.end_date
            else None
        ),
        "created_at": (
            subscription.created_at.isoformat()
            if getattr(subscription, "created_at", None)
            else None
        ),
        "plan": {
            "id": plan.id,
            "name_en": plan.name_en,
            "name_ar": getattr(plan, "name_ar", None),
        },
    }


def build_delivery_preferences(
    db: Session,
    user_id: int,
) -> list[dict]:
    """
    Return all delivery preferences for a user,
    including the meal category information.
    """

    rows = (
        db.query(
            UserCategoryDeliveryPreference,
            MealCategory,
        )
        .join(
            MealCategory,
            MealCategory.id
            == UserCategoryDeliveryPreference.meal_category_id,
        )
        .filter(
            UserCategoryDeliveryPreference.user_id == user_id,
        )
        .order_by(
            UserCategoryDeliveryPreference.id.asc(),
        )
        .all()
    )

    preferences = []

    for preference, category in rows:
        preferences.append(
            {
                "id": preference.id,
                "meal_category_id": preference.meal_category_id,
                "category": {
                    "id": category.id,
                    "name_en": category.name_en,
                    "name_ar": getattr(
                        category,
                        "name_ar",
                        None,
                    ),
                    "image_url": getattr(
                        category,
                        "image_url",
                        None,
                    ),
                },
                "place_type": enum_value(
                    preference.place_type
                ),
                "place_name": preference.place_name,
                "city": preference.city,
                "delivery_area": preference.delivery_area,
                "delivery_address": (
                    preference.delivery_address
                ),
                "latitude": preference.latitude,
                "longitude": preference.longitude,
                "preferred_delivery_time": (
                    preference.preferred_delivery_time.isoformat()
                    if preference.preferred_delivery_time
                    else None
                ),
                "delivery_note": preference.delivery_note,
                "is_active": preference.is_active,
                "created_at": (
                    preference.created_at.isoformat()
                    if preference.created_at
                    else None
                ),
                "updated_at": (
                    preference.updated_at.isoformat()
                    if preference.updated_at
                    else None
                ),
            }
        )

    return preferences


def build_complete_profile(
    db: Session,
    user: User,
) -> dict:
    """
    Build one complete user profile response.

    The response includes:
    - user information
    - health information
    - order statistics
    - subscription
    - delivery preferences
    """

    orders_count = (
        db.query(func.count(Order.id))
        .filter(Order.user_id == user.id)
        .scalar()
        or 0
    )

    total_spent = (
        db.query(
            func.coalesce(
                func.sum(Order.total_amount),
                0,
            )
        )
        .filter(Order.user_id == user.id)
        .scalar()
        or 0
    )

    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "location": user.location,
        "address": user.address,
        "gender": enum_value(user.gender),
        "age": user.age,
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "fitness_goal": enum_value(
            user.fitness_goal
        ),
        "dietary_preference": (
            user.dietary_preference
        ),
        "allergies": user.allergies or [],
        "role": enum_value(user.role),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at
            else None
        ),
        "updated_at": (
            user.updated_at.isoformat()
            if user.updated_at
            else None
        ),
        "orders_count": int(orders_count),
        "total_spent": float(total_spent),
        "subscription": build_subscription_data(
            db=db,
            user_id=user.id,
        ),
        "delivery_preferences": (
            build_delivery_preferences(
                db=db,
                user_id=user.id,
            )
        ),
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def my_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Return the current user's basic profile.
    """

    return current_user


@router.get("/me/profile")
def get_my_complete_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all current user information using one endpoint.

    This endpoint returns:
    - personal information
    - health information
    - subscription
    - order statistics
    - category delivery preferences
    """

    return build_complete_profile(
        db=db,
        user=current_user,
    )


@router.put("/me/profile")
def update_my_complete_profile(
    payload: CompleteProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the current user's profile and delivery
    preferences using one endpoint.
    """

    payload_data = payload.model_dump(
        exclude_unset=True,
    )

    delivery_preferences_data = payload_data.pop(
        "delivery_preferences",
        None,
    )


    new_phone = payload_data.get("phone")

    if new_phone is not None:
        normalized_phone = normalize_phone(new_phone)

        phone_owner = (
            db.query(User)
            .filter(
                User.phone == normalized_phone,
                User.id != current_user.id,
            )
            .first()
        )

        if phone_owner:
            raise HTTPException(
                status_code=409,
                detail="Phone number is already used by another user",
            )

        payload_data["phone"] = normalized_phone

    text_fields = [
        "first_name",
        "last_name",
        "location",
        "address",
        "dietary_preference",
    ]

    for field_name in text_fields:
        if field_name not in payload_data:
            continue

        value = payload_data[field_name]

        if field_name in ["first_name", "last_name"]:
            if value is not None:
                payload_data[field_name] = value.strip()
        else:
            payload_data[field_name] = clean_optional_text(
                value
            )

    for field_name, value in payload_data.items():
        setattr(
            current_user,
            field_name,
            value,
        )

    if delivery_preferences_data is not None:
        received_category_ids = set()

        for preference_data in delivery_preferences_data:
            meal_category_id = preference_data[
                "meal_category_id"
            ]

            if meal_category_id in received_category_ids:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "The same meal category cannot be "
                        "submitted more than once"
                    ),
                )

            received_category_ids.add(
                meal_category_id
            )

            category = (
                db.query(MealCategory)
                .filter(
                    MealCategory.id == meal_category_id,
                )
                .first()
            )

            if category is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Meal category {meal_category_id} "
                        "was not found"
                    ),
                )

            if hasattr(category, "is_active"):
                if category.is_active is False:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Meal category {meal_category_id} "
                            "is inactive"
                        ),
                    )

            existing_preference = (
                db.query(
                    UserCategoryDeliveryPreference
                )
                .filter(
                    UserCategoryDeliveryPreference.user_id
                    == current_user.id,
                    UserCategoryDeliveryPreference.meal_category_id
                    == meal_category_id,
                )
                .first()
            )

            if existing_preference is None:
                new_preference = (
                    UserCategoryDeliveryPreference(
                        user_id=current_user.id,
                        meal_category_id=meal_category_id,
                        place_type=preference_data[
                            "place_type"
                        ],
                        place_name=clean_optional_text(
                            preference_data.get(
                                "place_name"
                            )
                        ),
                        city=preference_data[
                            "city"
                        ].strip(),
                        delivery_area=preference_data[
                            "delivery_area"
                        ].strip(),
                        delivery_address=preference_data[
                            "delivery_address"
                        ].strip(),
                        latitude=preference_data.get(
                            "latitude"
                        ),
                        longitude=preference_data.get(
                            "longitude"
                        ),
                        preferred_delivery_time=(
                            preference_data[
                                "preferred_delivery_time"
                            ]
                        ),
                        delivery_note=clean_optional_text(
                            preference_data.get(
                                "delivery_note"
                            )
                        ),
                        is_active=True,
                    )
                )

                db.add(new_preference)

            else:
                existing_preference.place_type = (
                    preference_data["place_type"]
                )

                existing_preference.place_name = (
                    clean_optional_text(
                        preference_data.get(
                            "place_name"
                        )
                    )
                )

                existing_preference.city = (
                    preference_data["city"].strip()
                )

                existing_preference.delivery_area = (
                    preference_data[
                        "delivery_area"
                    ].strip()
                )

                existing_preference.delivery_address = (
                    preference_data[
                        "delivery_address"
                    ].strip()
                )

                existing_preference.latitude = (
                    preference_data.get(
                        "latitude"
                    )
                )

                existing_preference.longitude = (
                    preference_data.get(
                        "longitude"
                    )
                )

                existing_preference.preferred_delivery_time = (
                    preference_data[
                        "preferred_delivery_time"
                    ]
                )

                existing_preference.delivery_note = (
                    clean_optional_text(
                        preference_data.get(
                            "delivery_note"
                        )
                    )
                )

                existing_preference.is_active = True

    try:
        db.commit()
        db.refresh(current_user)

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Could not update profile because "
                "some information already exists"
            ),
        ) from error

    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Profile updated successfully",
        "data": build_complete_profile(
            db=db,
            user=current_user,
        ),
    }


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
    search: str | None = Query(
        None,
        description=(
            "Search by name, email, phone, or location"
        ),
    ),
    role: UserRole | None = Query(
        None,
        description="Filter by role",
    ),
    is_verified: bool | None = Query(
        None,
        description="Filter verified/unverified users",
    ),
    page: int = Query(
        1,
        ge=1,
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
    ),
):
    """
    Return users with pagination, subscription,
    order count and total amount spent.
    """

    query = db.query(User)

    if search:
        search_value = f"%{search.strip()}%"

        query = query.filter(
            or_(
                User.first_name.ilike(search_value),
                User.last_name.ilike(search_value),
                User.email.ilike(search_value),
                User.phone.ilike(search_value),
                User.location.ilike(search_value),
            )
        )

    if role:
        query = query.filter(
            User.role == role
        )

    if is_verified is not None:
        query = query.filter(
            User.is_verified == is_verified
        )

    total = query.count()

    users = (
        query.order_by(
            User.id.desc()
        )
        .offset(
            (page - 1) * limit
        )
        .limit(limit)
        .all()
    )

    user_ids = [
        user.id
        for user in users
    ]

    orders_counts = {}
    total_spents = {}

    if user_ids:
        order_statistics = (
            db.query(
                Order.user_id,
                func.count(
                    Order.id
                ).label("orders_count"),
                func.coalesce(
                    func.sum(
                        Order.total_amount
                    ),
                    0,
                ).label("total_spent"),
            )
            .filter(
                Order.user_id.in_(user_ids)
            )
            .group_by(
                Order.user_id
            )
            .all()
        )

        for row in order_statistics:
            orders_counts[row.user_id] = int(
                row.orders_count
            )

            total_spents[row.user_id] = float(
                row.total_spent
            )

    subscriptions_information = {}

    if user_ids:
        subscription_rows = (
            db.query(
                Subscription.user_id.label(
                    "subscription_user_id"
                ),
                Subscription.id.label(
                    "subscription_id"
                ),
                Subscription.status.label(
                    "subscription_status"
                ),
                Subscription.amount.label(
                    "subscription_amount"
                ),
                Subscription.start_date.label(
                    "subscription_start_date"
                ),
                Subscription.end_date.label(
                    "subscription_end_date"
                ),
                Subscription.payment_status.label(
                    "subscription_payment_status"
                ),
                MealPlan.id.label(
                    "plan_id"
                ),
                MealPlan.name_en.label(
                    "plan_name"
                ),
            )
            .join(
                MealPlan,
                Subscription.plan_id
                == MealPlan.id,
            )
            .filter(
                Subscription.user_id.in_(
                    user_ids
                )
            )
            .order_by(
                Subscription.id.desc()
            )
            .all()
        )

        for row in subscription_rows:
            user_id = row.subscription_user_id

            should_replace = (
                user_id not in subscriptions_information
                or row.subscription_status
                == SubscriptionStatus.ACTIVE
            )

            if should_replace:
                subscriptions_information[user_id] = {
                    "id": row.subscription_id,
                    "status": enum_value(
                        row.subscription_status
                    ),
                    "payment_status": enum_value(
                        row.subscription_payment_status
                    ),
                    "amount": (
                        float(
                            row.subscription_amount
                        )
                        if row.subscription_amount
                        is not None
                        else 0.0
                    ),
                    "start_date": (
                        row.subscription_start_date.isoformat()
                        if row.subscription_start_date
                        else None
                    ),
                    "end_date": (
                        row.subscription_end_date.isoformat()
                        if row.subscription_end_date
                        else None
                    ),
                    "plan": {
                        "id": row.plan_id,
                        "name_en": row.plan_name,
                    },
                }

    data = []

    for user in users:
        data.append(
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "location": user.location,
                "address": user.address,
                "gender": enum_value(
                    user.gender
                ),
                "age": user.age,
                "height_cm": user.height_cm,
                "weight_kg": user.weight_kg,
                "fitness_goal": enum_value(
                    user.fitness_goal
                ),
                "dietary_preference": (
                    user.dietary_preference
                ),
                "allergies": user.allergies or [],
                "role": enum_value(
                    user.role
                ),
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": (
                    user.created_at.isoformat()
                    if user.created_at
                    else None
                ),
                "orders_count": (
                    orders_counts.get(
                        user.id,
                        0,
                    )
                ),
                "total_spent": (
                    total_spents.get(
                        user.id,
                        0.0,
                    )
                ),
                "subscription": (
                    subscriptions_information.get(
                        user.id
                    )
                ),
            }
        )

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (
                (total + limit - 1) // limit
            ),
        },
    }


@router.get("/{user_id}/profile")
def get_user_complete_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
            UserRole.NUTRITION_MANAGER,
            UserRole.DELIVERY_MANAGER,
        )
    ),
):
    """
    Return one complete user profile for staff.

    Nutrition and delivery managers can access this
    endpoint because they need health or delivery details.
    """

    user = get_user_by_id(
        db=db,
        user_id=user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return build_complete_profile(
        db=db,
        user=user,
    )


@router.get("/{user_id}")
def show_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    """
    Return complete details for one user.
    """

    user = get_user_by_id(
        db=db,
        user_id=user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return build_complete_profile(
        db=db,
        user=user,
    )

@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: int,
    payload: UserUpdateRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.SUPER_ADMIN,
        )
    ),
):
    user = get_user_by_id(
        db=db,
        user_id=user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.role = payload.role

    db.commit()
    db.refresh(user)

    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    user = get_user_by_id(
        db=db,
        user_id=user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    if "email" in update_data:
        normalized_email = (
            str(update_data["email"])
            .strip()
            .lower()
        )

        email_owner = (
            db.query(User)
            .filter(
                User.email == normalized_email,
                User.id != user.id,
            )
            .first()
        )

        if email_owner:
            raise HTTPException(
                status_code=409,
                detail="Email is already used by another user",
            )

        update_data["email"] = normalized_email

    if "phone" in update_data:
        normalized_phone = normalize_phone(
            update_data["phone"]
        )

        phone_owner = (
            db.query(User)
            .filter(
                User.phone == normalized_phone,
                User.id != user.id,
            )
            .first()
        )

        if phone_owner:
            raise HTTPException(
                status_code=409,
                detail="Phone number is already used by another user",
            )

        update_data["phone"] = normalized_phone

    for field_name, value in update_data.items():
        setattr(
            user,
            field_name,
            value,
        )

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError as error:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email or phone number already exists",
        ) from error

    return user


@router.delete("/me/delivery-preferences/{preference_id}")
def delete_my_delivery_preference(
    preference_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete one delivery preference belonging
    to the current user.
    """

    preference = (
        db.query(
            UserCategoryDeliveryPreference
        )
        .filter(
            UserCategoryDeliveryPreference.id
            == preference_id,
            UserCategoryDeliveryPreference.user_id
            == current_user.id,
        )
        .first()
    )

    if preference is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery preference not found",
        )

    db.delete(preference)
    db.commit()

    return {
        "success": True,
        "message": "Delivery preference deleted successfully",
    }



@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.SUPER_ADMIN,
        )
    ),
):
    """
    Soft delete a user by deactivating their account.
    """

    user = get_user_by_id(
        db=db,
        user_id=user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.is_active = False

    db.commit()

    return {
        "success": True,
        "message": "User deactivated successfully",
    }