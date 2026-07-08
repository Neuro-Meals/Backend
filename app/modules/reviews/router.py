from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.reviews.models import Review
from app.modules.reviews.schemas import ReviewCreate, ReviewResponse, ReviewUpdate
from app.modules.users.models import User, UserRole


router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("/", response_model=ReviewResponse)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not any([payload.meal_id, payload.plan_id, payload.order_id, payload.delivery_id]):
        raise HTTPException(status_code=400, detail="Review must belong to meal, plan, order, or delivery")

    review = Review(
        user_id=current_user.id,
        **payload.model_dump(),
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return review


@router.get("/my", response_model=list[ReviewResponse])
def my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Review)
        .filter(Review.user_id == current_user.id)
        .order_by(Review.id.desc())
        .all()
    )


@router.get("/")
def list_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    meal_id: int | None = Query(None),
    plan_id: int | None = Query(None),
    rating: int | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    query = db.query(Review)

    if meal_id:
        query = query.filter(Review.meal_id == meal_id)

    if plan_id:
        query = query.filter(Review.plan_id == plan_id)

    if rating:
        query = query.filter(Review.rating == rating)

    total = query.count()

    reviews = (
        query.order_by(Review.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "data": reviews,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
        },
    }


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if current_user.role == UserRole.CUSTOMER and review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return review


@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: int,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.user_id == current_user.id,
    ).first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review, field, value)

    db.commit()
    db.refresh(review)

    return review


@router.delete("/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    review = db.query(Review).filter(Review.id == review_id).first()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if current_user.role == UserRole.CUSTOMER and review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    db.delete(review)
    db.commit()

    return {"message": "Review deleted successfully"}