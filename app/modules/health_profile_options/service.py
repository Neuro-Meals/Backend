from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.health_profile_options.models import HealthProfileOption
from app.modules.health_profile_options.schemas import (
    HealthProfileOptionCreate,
    HealthProfileOptionType,
    HealthProfileOptionUpdate,
)


def get_option_or_404(db: Session, option_id: int) -> HealthProfileOption:
    option = (
        db.query(HealthProfileOption)
        .filter(HealthProfileOption.id == option_id)
        .first()
    )
    if not option:
        raise HTTPException(status_code=404, detail="Health profile option not found")
    return option


def ensure_unique(
    db: Session,
    option_type: str,
    value: str,
    exclude_id: int | None = None,
) -> None:
    query = db.query(HealthProfileOption).filter(
        HealthProfileOption.option_type == option_type,
        func.lower(HealthProfileOption.value) == value.lower(),
    )
    if exclude_id is not None:
        query = query.filter(HealthProfileOption.id != exclude_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An option with this type and value already exists",
        )


def create_option(db: Session, payload: HealthProfileOptionCreate) -> HealthProfileOption:
    ensure_unique(db, payload.option_type.value, payload.value)
    option = HealthProfileOption(**payload.model_dump(mode="json"))
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def update_option(
    db: Session,
    option: HealthProfileOption,
    payload: HealthProfileOptionUpdate,
) -> HealthProfileOption:
    changes = payload.model_dump(exclude_unset=True, mode="json")
    new_type = changes.get("option_type", option.option_type)
    new_value = changes.get("value", option.value)
    ensure_unique(db, new_type, new_value, exclude_id=option.id)

    for field, value in changes.items():
        setattr(option, field, value)

    db.commit()
    db.refresh(option)
    return option


def list_options(
    db: Session,
    option_type: HealthProfileOptionType | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 100,
) -> tuple[list[HealthProfileOption], int]:
    query = db.query(HealthProfileOption)

    if option_type is not None:
        query = query.filter(HealthProfileOption.option_type == option_type.value)
    if is_active is not None:
        query = query.filter(HealthProfileOption.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                HealthProfileOption.value.ilike(term),
                HealthProfileOption.label_en.ilike(term),
                HealthProfileOption.label_ar.ilike(term),
                HealthProfileOption.description.ilike(term),
            )
        )

    total = query.count()
    rows = (
        query.order_by(
            HealthProfileOption.option_type.asc(),
            HealthProfileOption.sort_order.asc(),
            HealthProfileOption.label_en.asc(),
            HealthProfileOption.id.asc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return rows, total


def public_grouped_options(db: Session) -> dict[str, list[HealthProfileOption]]:
    rows = (
        db.query(HealthProfileOption)
        .filter(HealthProfileOption.is_active.is_(True))
        .order_by(
            HealthProfileOption.option_type.asc(),
            HealthProfileOption.sort_order.asc(),
            HealthProfileOption.label_en.asc(),
        )
        .all()
    )

    grouped: dict[str, list[HealthProfileOption]] = {
        "dietary_preferences": [],
        "allergies": [],
        "health_conditions": [],
    }
    key_map = {
        HealthProfileOptionType.DIETARY_PREFERENCE.value: "dietary_preferences",
        HealthProfileOptionType.ALLERGY.value: "allergies",
        HealthProfileOptionType.HEALTH_CONDITION.value: "health_conditions",
    }
    for row in rows:
        key = key_map.get(row.option_type)
        if key:
            grouped[key].append(row)
    return grouped
