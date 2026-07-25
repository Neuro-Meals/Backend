from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.modules.meal_assignments.models import (
    MealAssignment,
    MealAssignmentItem,
)
from app.modules.meal_assignments.service import (
    clean_optional_text,
    get_driver_or_404,
    get_meal_or_404,
    validate_meal_matches_category,
)
from app.modules.meals.models import Meal, MealCategory
from app.modules.nutrition.schemas import (
    CustomWeeksConfiguration,
    DayMenu,
    MealCategories,
    MealCategoryAssignment,
    MenuGenerationMode,
    MenuGenerationRequest,
    RepeatWeekConfiguration,
    SingleDayConfiguration,
)
from app.modules.orders.models import Order
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import (
    User,
    UserCategoryDeliveryPreference,
)


MEAL_TIMES = (
    "breakfast",
    "lunch",
    "dinner",
    "snack",
)


class MenuGenerator:
    """
    Generate production meal assignments for a subscription.

    MealAssignment is the source of truth used by the order automation:

        MenuGenerator
            -> MealAssignment
            -> MealAssignmentItem
            -> automatic Order generation
            -> Delivery tracking

    Driver assignment is planned here. The driver can act only after the chef
    changes the order to READY_FOR_DELIVERY.
    """

    def __init__(
        self,
        db: Session,
        subscription: Subscription,
        admin: User,
    ):
        self.db = db
        self.subscription = subscription
        self.admin = admin

    def generate(self, payload: MenuGenerationRequest) -> dict:
        self._validate_subscription()

        subscription_days = self._get_subscription_days()
        category_map = self._get_category_map()

        if payload.mode == MenuGenerationMode.SINGLE_DAY:
            schedule = self._build_single_day_schedule(
                configuration=payload.single_day,
                subscription_days=subscription_days,
            )
        elif payload.mode == MenuGenerationMode.REPEAT_WEEK:
            schedule = self._build_repeat_week_schedule(
                configuration=payload.repeat_week,
                subscription_days=subscription_days,
            )
        elif payload.mode == MenuGenerationMode.CUSTOM_WEEKS:
            schedule = self._build_custom_weeks_schedule(
                configuration=payload.custom_weeks,
                subscription_days=subscription_days,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported menu generation mode",
            )

        return self._save_schedule(
            mode=payload.mode,
            schedule=schedule,
            category_map=category_map,
            replace_existing=payload.replace_existing,
            subscription_days=subscription_days,
        )

    def _build_single_day_schedule(
        self,
        configuration: SingleDayConfiguration | None,
        subscription_days: int,
    ) -> dict[int, MealCategories]:
        if configuration is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="single_day configuration is required",
            )

        self._validate_absolute_day_number(
            day_number=configuration.day_number,
            subscription_days=subscription_days,
        )

        return {configuration.day_number: configuration.categories}

    def _build_repeat_week_schedule(
        self,
        configuration: RepeatWeekConfiguration | None,
        subscription_days: int,
    ) -> dict[int, MealCategories]:
        if configuration is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="repeat_week configuration is required",
            )

        template_by_day: dict[int, DayMenu] = {
            day.day_number: day for day in configuration.days
        }

        generated_schedule: dict[int, MealCategories] = {}

        for absolute_day in range(1, subscription_days + 1):
            template_day_number = ((absolute_day - 1) % 7) + 1
            generated_schedule[absolute_day] = template_by_day[
                template_day_number
            ].categories

        return generated_schedule

    def _build_custom_weeks_schedule(
        self,
        configuration: CustomWeeksConfiguration | None,
        subscription_days: int,
    ) -> dict[int, MealCategories]:
        if configuration is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="custom_weeks configuration is required",
            )

        required_week_count = ceil(subscription_days / 7)
        submitted_weeks = {
            week.week_number: week for week in configuration.weeks
        }

        expected_week_numbers = set(range(1, required_week_count + 1))
        submitted_week_numbers = set(submitted_weeks)

        missing_weeks = sorted(
            expected_week_numbers - submitted_week_numbers
        )
        unexpected_weeks = sorted(
            submitted_week_numbers - expected_week_numbers
        )

        if missing_weeks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": (
                        "Menus must be provided for every subscription week"
                    ),
                    "required_week_count": required_week_count,
                    "missing_weeks": missing_weeks,
                },
            )

        if unexpected_weeks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": (
                        "Some submitted weeks are outside the subscription "
                        "duration"
                    ),
                    "unexpected_weeks": unexpected_weeks,
                    "maximum_week": required_week_count,
                },
            )

        generated_schedule: dict[int, MealCategories] = {}

        for week_number in range(1, required_week_count + 1):
            week = submitted_weeks[week_number]
            day_templates = {day.day_number: day for day in week.days}

            first_absolute_day = ((week_number - 1) * 7) + 1
            last_absolute_day = min(
                first_absolute_day + 6,
                subscription_days,
            )
            required_days_in_week = (
                last_absolute_day - first_absolute_day + 1
            )

            expected_template_days = set(
                range(1, required_days_in_week + 1)
            )
            submitted_template_days = set(day_templates)
            missing_days = sorted(
                expected_template_days - submitted_template_days
            )
            unexpected_days = sorted(
                submitted_template_days - expected_template_days
            )

            if missing_days:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": (
                            f"Week {week_number} does not contain all "
                            "required subscription days"
                        ),
                        "missing_day_numbers": missing_days,
                    },
                )

            if unexpected_days:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": (
                            f"Week {week_number} contains days outside the "
                            "subscription duration"
                        ),
                        "unexpected_day_numbers": unexpected_days,
                    },
                )

            for template_day_number in range(
                1,
                required_days_in_week + 1,
            ):
                absolute_day_number = (
                    first_absolute_day + template_day_number - 1
                )
                generated_schedule[absolute_day_number] = day_templates[
                    template_day_number
                ].categories

        return generated_schedule

    def _save_schedule(
        self,
        mode: MenuGenerationMode,
        schedule: dict[int, MealCategories],
        category_map: dict[str, MealCategory],
        replace_existing: bool,
        subscription_days: int,
    ) -> dict:
        target_days = sorted(schedule)
        target_dates = [self._scheduled_date(day) for day in target_days]

        requested_assignment_count = sum(
            categories.assignment_count()
            for categories in schedule.values()
        )
        requested_category_count = sum(
            categories.active_category_count()
            for categories in schedule.values()
        )

        created_count = 0
        updated_count = 0
        deleted_count = 0
        skipped_count = 0
        saved_assignment_ids: list[int] = []

        try:
            existing_assignments = (
                self.db.query(MealAssignment)
                .filter(
                    MealAssignment.subscription_id == self.subscription.id,
                    MealAssignment.delivery_date.in_(target_dates),
                )
                .all()
            )

            existing_by_key = {
                (
                    assignment.delivery_date,
                    assignment.meal_category_id,
                ): assignment
                for assignment in existing_assignments
            }

            if replace_existing and existing_assignments:
                self._ensure_assignments_have_no_orders(
                    existing_assignments
                )

                for assignment in existing_assignments:
                    self.db.delete(assignment)

                deleted_count = len(existing_assignments)
                self.db.flush()
                existing_by_key = {}

            preference_cache: dict[
                int,
                UserCategoryDeliveryPreference,
            ] = {}
            driver_cache: dict[int, User] = {}
            meal_cache: dict[int, Meal] = {}

            for day_number, categories in schedule.items():
                delivery_date = self._scheduled_date(day_number)

                for meal_time in MEAL_TIMES:
                    category_payload: MealCategoryAssignment = getattr(
                        categories,
                        meal_time,
                    )

                    if not category_payload.is_assigned:
                        continue

                    category = category_map[meal_time]
                    preference = self._get_delivery_preference(
                        category=category,
                        cache=preference_cache,
                    )
                    driver = self._get_driver(
                        driver_id=category_payload.driver_id,
                        cache=driver_cache,
                    )
                    validated_meals = self._get_validated_meals(
                        meal_ids=category_payload.meal_ids,
                        category=category,
                        cache=meal_cache,
                    )

                    key = (delivery_date, category.id)
                    assignment = existing_by_key.get(key)

                    if assignment is None:
                        assignment = MealAssignment(
                            user_id=self.subscription.user_id,
                            subscription_id=self.subscription.id,
                            meal_category_id=category.id,
                            delivery_preference_id=preference.id,
                            driver_id=driver.id,
                            delivery_date=delivery_date,
                            delivery_time=(
                                preference.preferred_delivery_time
                            ),
                            notes=clean_optional_text(
                                category_payload.notes
                            ),
                            assigned_by=self.admin.id,
                            is_active=True,
                        )
                        self.db.add(assignment)
                        self.db.flush()
                        created_count += 1
                    else:
                        self._ensure_assignment_has_no_order(assignment)

                        assignment.user_id = self.subscription.user_id
                        assignment.delivery_preference_id = preference.id
                        assignment.driver_id = driver.id
                        assignment.delivery_time = (
                            preference.preferred_delivery_time
                        )
                        assignment.notes = clean_optional_text(
                            category_payload.notes
                        )
                        assignment.assigned_by = self.admin.id
                        assignment.is_active = True
                        assignment.updated_at = datetime.utcnow()

                        self._delete_assignment_items(assignment.id)
                        updated_count += 1

                    for meal in validated_meals:
                        self.db.add(
                            MealAssignmentItem(
                                meal_assignment_id=assignment.id,
                                meal_id=meal.id,
                                quantity=1,
                            )
                        )

                    self.db.flush()
                    existing_by_key[key] = assignment
                    saved_assignment_ids.append(assignment.id)

            self.db.commit()

        except HTTPException:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "A menu assignment conflicts with an existing assignment"
                ),
            ) from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate the subscription menu",
            ) from exc

        generated_days = self._serialize_generated_days(
            target_days=target_days,
        )

        return {
            "success": True,
            "message": (
                "Production menu generated successfully for "
                f"{len(target_days)} subscription day(s)"
            ),
            "mode": mode,
            "subscription_id": self.subscription.id,
            "user_id": self.subscription.user_id,
            "plan_id": self.subscription.plan_id,
            "subscription_days": subscription_days,
            "generated_day_count": len(target_days),
            "replace_existing": replace_existing,
            "requested_assignment_count": requested_assignment_count,
            "requested_category_count": requested_category_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "deleted_count": deleted_count,
            "skipped_count": skipped_count,
            "generated_days": generated_days,
        }

    def _validate_subscription(self) -> None:
        if self.subscription.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The subscription must be active",
            )

        if self.subscription.payment_status != PaymentStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The subscription must be paid",
            )

        if self.subscription.start_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The subscription does not have a start date",
            )

        if self.subscription.end_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The subscription does not have an end date",
            )

        if self.subscription.end_date < self.subscription.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The subscription date range is invalid",
            )

    def _get_subscription_days(self) -> int:
        start_date = self._date_only(self.subscription.start_date)
        end_date = self._date_only(self.subscription.end_date)
        return (end_date - start_date).days + 1

    def _validate_absolute_day_number(
        self,
        day_number: int,
        subscription_days: int,
    ) -> None:
        if day_number > subscription_days:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Subscription day {day_number} is outside the "
                    f"{subscription_days}-day subscription"
                ),
            )

    def _get_category_map(self) -> dict[str, MealCategory]:
        categories = (
            self.db.query(MealCategory)
            .filter(MealCategory.is_active.is_(True))
            .all()
        )

        category_map: dict[str, MealCategory] = {}

        for category in categories:
            normalized_name = self._normalize_category_name(
                getattr(category, "name_en", "")
            )

            if normalized_name in MEAL_TIMES:
                if normalized_name in category_map:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "More than one active meal category matches "
                            f"'{normalized_name}'"
                        ),
                    )

                category_map[normalized_name] = category

        missing = sorted(set(MEAL_TIMES) - set(category_map))

        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": (
                        "Required active meal categories are missing"
                    ),
                    "missing_categories": missing,
                },
            )

        return category_map

    def _get_delivery_preference(
        self,
        category: MealCategory,
        cache: dict[int, UserCategoryDeliveryPreference],
    ) -> UserCategoryDeliveryPreference:
        if category.id in cache:
            return cache[category.id]

        preferences = (
            self.db.query(UserCategoryDeliveryPreference)
            .filter(
                UserCategoryDeliveryPreference.user_id
                == self.subscription.user_id,
                UserCategoryDeliveryPreference.meal_category_id
                == category.id,
                UserCategoryDeliveryPreference.is_active.is_(True),
            )
            .order_by(UserCategoryDeliveryPreference.id.asc())
            .all()
        )

        if not preferences:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The customer has no active delivery preference for "
                    f"{category.name_en}"
                ),
            )

        if len(preferences) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The customer has multiple active delivery preferences "
                    f"for {category.name_en}. Keep only one active preference."
                ),
            )

        preference = preferences[0]

        if not getattr(preference, "delivery_address", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The {category.name_en} delivery preference has no "
                    "delivery address"
                ),
            )

        if getattr(preference, "preferred_delivery_time", None) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"The {category.name_en} delivery preference has no "
                    "preferred delivery time"
                ),
            )

        cache[category.id] = preference
        return preference

    def _get_driver(
        self,
        driver_id: int | None,
        cache: dict[int, User],
    ) -> User:
        if driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="driver_id is required",
            )

        if driver_id not in cache:
            cache[driver_id] = get_driver_or_404(
                db=self.db,
                driver_id=driver_id,
            )

        return cache[driver_id]

    def _get_validated_meals(
        self,
        meal_ids: list[int],
        category: MealCategory,
        cache: dict[int, Meal],
    ) -> list[Meal]:
        validated: list[Meal] = []

        for meal_id in meal_ids:
            if meal_id not in cache:
                cache[meal_id] = get_meal_or_404(
                    db=self.db,
                    meal_id=meal_id,
                )

            meal = cache[meal_id]
            validate_meal_matches_category(
                meal=meal,
                category_id=category.id,
            )
            validated.append(meal)

        return validated

    def _ensure_assignments_have_no_orders(
        self,
        assignments: list[MealAssignment],
    ) -> None:
        assignment_ids = [assignment.id for assignment in assignments]

        order = (
            self.db.query(Order)
            .filter(Order.meal_assignment_id.in_(assignment_ids))
            .first()
        )

        if order is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This menu cannot be replaced because one or more "
                    "assignments already produced orders. Update dispatch or "
                    "cancel the affected orders first."
                ),
            )

    def _ensure_assignment_has_no_order(
        self,
        assignment: MealAssignment,
    ) -> None:
        order_exists = (
            self.db.query(Order.id)
            .filter(Order.meal_assignment_id == assignment.id)
            .first()
        )

        if order_exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This assignment already produced an order and can no "
                    "longer be changed through menu generation"
                ),
            )

    def _delete_assignment_items(self, assignment_id: int) -> None:
        (
            self.db.query(MealAssignmentItem)
            .filter(
                MealAssignmentItem.meal_assignment_id == assignment_id
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()

    def _serialize_generated_days(
        self,
        target_days: list[int],
    ) -> list[dict]:
        target_dates = [self._scheduled_date(day) for day in target_days]

        assignments = (
            self.db.query(MealAssignment)
            .options(
                selectinload(MealAssignment.items).selectinload(
                    MealAssignmentItem.meal
                ),
                selectinload(MealAssignment.category),
                selectinload(MealAssignment.driver),
                selectinload(MealAssignment.delivery_preference),
            )
            .filter(
                MealAssignment.subscription_id == self.subscription.id,
                MealAssignment.delivery_date.in_(target_dates),
                MealAssignment.is_active.is_(True),
            )
            .order_by(
                MealAssignment.delivery_date.asc(),
                MealAssignment.meal_category_id.asc(),
            )
            .all()
        )

        assignments_by_date: dict[date, list[MealAssignment]] = {}
        for assignment in assignments:
            assignments_by_date.setdefault(
                assignment.delivery_date,
                [],
            ).append(assignment)

        result: list[dict] = []

        for day_number in target_days:
            scheduled_date = self._scheduled_date(day_number)
            day_assignments: dict[str, dict] = {}

            for assignment in assignments_by_date.get(
                scheduled_date,
                [],
            ):
                meal_time = self._normalize_category_name(
                    assignment.category.name_en
                )
                day_assignments[meal_time] = self._serialize_assignment(
                    assignment=assignment,
                    meal_time=meal_time,
                )

            result.append(
                {
                    "day_number": day_number,
                    "scheduled_date": scheduled_date,
                    "assignments": day_assignments,
                }
            )

        return result

    def _serialize_assignment(
        self,
        assignment: MealAssignment,
        meal_time: str,
    ) -> dict:
        driver = assignment.driver
        preference = assignment.delivery_preference
        category = assignment.category

        return {
            "assignment_id": assignment.id,
            "meal_time": meal_time,
            "meal_category_id": assignment.meal_category_id,
            "category_name": getattr(category, "name_en", None),
            "category_name_ar": getattr(category, "name_ar", None),
            "delivery_date": assignment.delivery_date,
            "delivery_time": assignment.delivery_time,
            "notes": assignment.notes,
            "is_active": assignment.is_active,
            "driver": {
                "id": driver.id,
                "first_name": getattr(driver, "first_name", None),
                "last_name": getattr(driver, "last_name", None),
                "full_name": self._full_name(driver),
                "phone": getattr(driver, "phone", None),
                "email": getattr(driver, "email", None),
            },
            "delivery_preference": {
                "id": preference.id,
                "meal_category_id": preference.meal_category_id,
                "place_type": self._enum_value(
                    getattr(preference, "place_type", None)
                ),
                "place_name": getattr(preference, "place_name", None),
                "city": getattr(preference, "city", None),
                "delivery_area": getattr(
                    preference,
                    "delivery_area",
                    None,
                ),
                "delivery_address": preference.delivery_address,
                "latitude": getattr(preference, "latitude", None),
                "longitude": getattr(preference, "longitude", None),
                "preferred_delivery_time": (
                    preference.preferred_delivery_time
                ),
                "delivery_note": getattr(
                    preference,
                    "delivery_note",
                    None,
                ),
            },
            "meals": [
                {
                    "item_id": item.id,
                    "meal_id": item.meal_id,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "meal": self._serialize_meal(item.meal),
                }
                for item in assignment.items
            ],
        }

    @staticmethod
    def _serialize_meal(meal: Meal) -> dict:
        return {
            "id": meal.id,
            "category_id": meal.category_id,
            "name_en": meal.name_en,
            "name_ar": getattr(meal, "name_ar", None),
            "description_en": getattr(meal, "description_en", None),
            "description_ar": getattr(meal, "description_ar", None),
            "calories": meal.calories,
            "protein_g": meal.protein_g,
            "carbs_g": meal.carbs_g,
            "fat_g": meal.fat_g,
            "fiber_g": getattr(meal, "fiber_g", None),
            "sugar_g": getattr(meal, "sugar_g", None),
            "sodium_mg": getattr(meal, "sodium_mg", None),
            "price": meal.price,
            "image_url": getattr(meal, "image_url", None),
            "ingredients": getattr(meal, "ingredients", None) or [],
            "allergens": getattr(meal, "allergens", None) or [],
            "diet_tags": getattr(meal, "diet_tags", None) or [],
        }

    def _scheduled_date(self, day_number: int) -> date:
        start_date = self._date_only(self.subscription.start_date)
        return start_date + timedelta(days=day_number - 1)

    @staticmethod
    def _date_only(value: date | datetime) -> date:
        if isinstance(value, datetime):
            return value.date()
        return value

    @staticmethod
    def _normalize_category_name(value: str) -> str:
        return (
            value.strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    @staticmethod
    def _enum_value(value):
        if value is None:
            return None
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _full_name(user: User) -> str | None:
        name = " ".join(
            part
            for part in (
                getattr(user, "first_name", None),
                getattr(user, "last_name", None),
            )
            if part
        ).strip()
        return name or None