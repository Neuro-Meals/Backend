from datetime import date, datetime, time, timedelta

from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine

from app.modules.meals.models import Meal, MealCategory
from app.modules.notifications.models import Notification
from app.modules.orders.automation_service import (
    confirm_scheduled_orders_for_date,
    generate_orders_for_date,
)
from app.modules.plan_menus.models import PlanMenuItem, WeekDay
from app.modules.plans.models import MealPlan, PlanGoal, PlanType
from app.modules.subscriptions.models import (
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.users.models import FitnessGoal, Gender, User, UserRole


PASSWORD = "Amro&258"

RIYADH_ADDRESSES = {
    "customer1@test.com": {
        "location": "Riyadh",
        "address": "King Fahd Road, Al Olaya, Riyadh",
        "allergies": [],
    },
    "customer2@test.com": {
        "location": "Riyadh",
        "address": "Prince Sultan Road, Riyadh",
        "allergies": ["nuts"],
    },
    "customer3@test.com": {
        "location": "Riyadh",
        "address": "King Abdullah Road, Riyadh",
        "allergies": ["dairy"],
    },
}


def enum_value(value):
    if value is None:
        return None
    return value.value if hasattr(value, "value") else value


def commit_and_refresh(db, instance):
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def get_or_create_user(
    db,
    *,
    first_name,
    last_name,
    email,
    phone,
    role,
    location="Riyadh",
    address="King Fahd Road, Riyadh",
    allergies=None,
):
    normalized_email = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if user is None:
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=normalized_email,
            phone=phone,
            hashed_password=hash_password(PASSWORD),
            role=role,
            is_active=True,
            is_verified=True,
            location=location,
            address=address,
            gender=Gender.MALE,
            age=25,
            height_cm=175,
            weight_kg=70,
            fitness_goal=FitnessGoal.MAINTENANCE,
            dietary_preference="balanced diet",
            allergies=allergies or [],
            created_at=datetime.utcnow(),
        )
    else:
        # Make the seed repeatable and repair old incomplete demo records.
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.role = role
        user.is_active = True
        user.is_verified = True
        user.location = location
        user.address = address
        user.allergies = allergies or []

    return commit_and_refresh(db, user)


def get_or_create_category(
    db,
    *,
    name_en,
    name_ar,
    image_url,
):
    category = (
        db.query(MealCategory)
        .filter(MealCategory.name_en == name_en)
        .first()
    )

    if category is None:
        category = MealCategory(
            name_en=name_en,
            name_ar=name_ar,
            description=f"{name_en} meals",
            image_url=image_url,
            is_active=True,
        )
    else:
        category.name_ar = name_ar
        category.description = f"{name_en} meals"
        category.image_url = image_url
        category.is_active = True

    return commit_and_refresh(db, category)


def get_or_create_meal(
    db,
    *,
    category_id,
    name_en,
    name_ar,
    price,
    calories,
    protein,
    carbs,
    fat,
    image_url,
    diet_tags,
    ingredients,
    allergens=None,
):
    meal = (
        db.query(Meal)
        .filter(Meal.name_en == name_en)
        .first()
    )

    values = {
        "category_id": category_id,
        "name_en": name_en,
        "name_ar": name_ar,
        "description_en": f"Healthy {name_en}",
        "description_ar": None,
        "calories": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
        "fiber_g": 5,
        "sugar_g": 3,
        "sodium_mg": 250,
        "price": price,
        "image_url": image_url,
        "ingredients": ingredients,
        "allergens": allergens or [],
        "diet_tags": diet_tags,
        "is_available": True,
    }

    if meal is None:
        meal = Meal(**values)
    else:
        for field, value in values.items():
            setattr(meal, field, value)

    return commit_and_refresh(db, meal)


def get_or_create_plan(
    db,
    *,
    name_en,
    name_ar,
    plan_type,
    goal,
    price,
    duration_days,
    meals_per_day,
    image_url,
):
    plan = (
        db.query(MealPlan)
        .filter(MealPlan.name_en == name_en)
        .first()
    )

    values = {
        "name_en": name_en,
        "name_ar": name_ar,
        "description_en": f"{name_en} subscription plan",
        "description_ar": None,
        "plan_type": plan_type,
        "goal": goal,
        "price": price,
        "duration_days": duration_days,
        "meals_per_day": meals_per_day,
        "total_meals": duration_days * meals_per_day,
        "image_url": image_url,
        "is_active": True,
    }

    if plan is None:
        plan = MealPlan(**values)
    else:
        for field, value in values.items():
            setattr(plan, field, value)

    return commit_and_refresh(db, plan)


def get_or_create_plan_menu_item(
    db,
    *,
    plan_id,
    meal_id,
    category_id,
    day_of_week,
    quantity=1,
    sort_order=0,
):
    menu_item = (
        db.query(PlanMenuItem)
        .filter(
            PlanMenuItem.plan_id == plan_id,
            PlanMenuItem.meal_id == meal_id,
            PlanMenuItem.category_id == category_id,
            PlanMenuItem.day_of_week == day_of_week,
        )
        .first()
    )

    if menu_item is None:
        menu_item = PlanMenuItem(
            plan_id=plan_id,
            meal_id=meal_id,
            category_id=category_id,
            day_of_week=day_of_week,
            quantity=quantity,
            sort_order=sort_order,
            is_active=True,
        )
    else:
        menu_item.quantity = quantity
        menu_item.sort_order = sort_order
        menu_item.is_active = True

    return commit_and_refresh(db, menu_item)


def get_or_create_active_subscription(
    db,
    *,
    user_id,
    plan,
    notes,
):
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.plan_id == plan.id,
        )
        .order_by(Subscription.id.desc())
        .first()
    )

    start_datetime = datetime.combine(date.today(), time.min)
    end_datetime = start_datetime + timedelta(days=plan.duration_days)

    if subscription is None:
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            payment_status=PaymentStatus.PAID,
            amount=plan.price,
            start_date=start_datetime,
            end_date=end_datetime,
            notes=notes,
        )
    else:
        # Convert any old pending demo subscription into an active paid one.
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.payment_status = PaymentStatus.PAID
        subscription.amount = plan.price
        subscription.start_date = start_datetime
        subscription.end_date = end_datetime
        subscription.paused_at = None
        subscription.cancelled_at = None
        subscription.notes = notes

    return commit_and_refresh(db, subscription)


def create_notification_once(
    db,
    *,
    user_id,
    title,
    message,
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.title == title,
        )
        .first()
    )

    if notification is not None:
        return notification

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type="general",
        channel="in_app",
        is_read=False,
    )

    return commit_and_refresh(db, notification)


def build_weekly_menus(
    db,
    *,
    plans,
    categories,
    meals,
):
    weekdays = [
        WeekDay.MONDAY,
        WeekDay.TUESDAY,
        WeekDay.WEDNESDAY,
        WeekDay.THURSDAY,
        WeekDay.FRIDAY,
        WeekDay.SATURDAY,
        WeekDay.SUNDAY,
    ]

    # Each plan receives breakfast, lunch and dinner for every weekday.
    plan_schedule = {
        plans["weight_loss"].id: [
            (meals["oats"].id, categories["breakfast"].id, 1),
            (meals["chicken_rice"].id, categories["lunch"].id, 2),
            (meals["salmon"].id, categories["dinner"].id, 3),
        ],
        plans["muscle_gain"].id: [
            (meals["egg_toast"].id, categories["breakfast"].id, 1),
            (meals["beef_quinoa"].id, categories["lunch"].id, 2),
            (meals["vegetable_pasta"].id, categories["dinner"].id, 3),
        ],
        plans["healthy"].id: [
            (meals["oats"].id, categories["breakfast"].id, 1),
            (meals["chicken_rice"].id, categories["lunch"].id, 2),
            (meals["vegetable_pasta"].id, categories["dinner"].id, 3),
        ],
    }

    for plan_id, daily_items in plan_schedule.items():
        for weekday in weekdays:
            for meal_id, category_id, sort_order in daily_items:
                get_or_create_plan_menu_item(
                    db,
                    plan_id=plan_id,
                    meal_id=meal_id,
                    category_id=category_id,
                    day_of_week=weekday,
                    quantity=1,
                    sort_order=sort_order,
                )


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ------------------------------------------------------------------
        # Users for all major role flows
        # ------------------------------------------------------------------
        admin = get_or_create_user(
            db,
            first_name="Admin",
            last_name="Test",
            email="nutriomeals0@gmail.com",
            phone="+966000000000",
            role=UserRole.ADMIN,
        )

        super_admin = get_or_create_user(
            db,
            first_name="Super Admin",
            last_name="Test",
            email="nutriomeals1@gmail.com",
            phone="+966000000001",
            role=UserRole.SUPER_ADMIN,
        )

        chef = get_or_create_user(
            db,
            first_name="Chef",
            last_name="Test",
            email="chef@test.com",
            phone="+966000000004",
            role=UserRole.CHEF,
        )

        driver = get_or_create_user(
            db,
            first_name="Driver",
            last_name="Test",
            email="driver@test.com",
            phone="+966000000003",
            role=UserRole.DRIVER,
        )

        customers = [
            get_or_create_user(
                db,
                first_name="Ahmed",
                last_name="Ali",
                email="customer1@test.com",
                phone="+966500000101",
                role=UserRole.CUSTOMER,
                **RIYADH_ADDRESSES["customer1@test.com"],
            ),
            get_or_create_user(
                db,
                first_name="Sara",
                last_name="Mohammed",
                email="customer2@test.com",
                phone="+966500000102",
                role=UserRole.CUSTOMER,
                **RIYADH_ADDRESSES["customer2@test.com"],
            ),
            get_or_create_user(
                db,
                first_name="Khalid",
                last_name="Omar",
                email="customer3@test.com",
                phone="+966500000103",
                role=UserRole.CUSTOMER,
                **RIYADH_ADDRESSES["customer3@test.com"],
            ),
        ]

        # ------------------------------------------------------------------
        # Meal categories
        # ------------------------------------------------------------------
        categories = {
            "breakfast": get_or_create_category(
                db,
                name_en="Breakfast",
                name_ar="فطور",
                image_url="/static/uploads/categories/breakfast.jpg",
            ),
            "lunch": get_or_create_category(
                db,
                name_en="Lunch",
                name_ar="غداء",
                image_url="/static/uploads/categories/lunch.jpg",
            ),
            "dinner": get_or_create_category(
                db,
                name_en="Dinner",
                name_ar="عشاء",
                image_url="/static/uploads/categories/dinner.jpg",
            ),
            "snacks": get_or_create_category(
                db,
                name_en="Snacks",
                name_ar="وجبات خفيفة",
                image_url="/static/uploads/categories/snacks.jpg",
            ),
        }

        # ------------------------------------------------------------------
        # Meals
        # ------------------------------------------------------------------
        meals = {
            "oats": get_or_create_meal(
                db,
                category_id=categories["breakfast"].id,
                name_en="Oats Banana Bowl",
                name_ar="وعاء الشوفان والموز",
                price=25,
                calories=350,
                protein=15,
                carbs=55,
                fat=8,
                image_url="/static/uploads/meals/oats.jpg",
                diet_tags=["weight_loss", "healthy_lifestyle"],
                ingredients=["oats", "banana", "milk"],
                allergens=["dairy"],
            ),
            "egg_toast": get_or_create_meal(
                db,
                category_id=categories["breakfast"].id,
                name_en="Egg Avocado Toast",
                name_ar="توست البيض والأفوكادو",
                price=30,
                calories=420,
                protein=22,
                carbs=35,
                fat=18,
                image_url="/static/uploads/meals/egg-toast.jpg",
                diet_tags=["high_protein"],
                ingredients=["egg", "avocado", "whole wheat bread"],
                allergens=["eggs", "gluten"],
            ),
            "chicken_rice": get_or_create_meal(
                db,
                category_id=categories["lunch"].id,
                name_en="Grilled Chicken Rice",
                name_ar="دجاج مشوي مع الأرز",
                price=45,
                calories=620,
                protein=48,
                carbs=60,
                fat=15,
                image_url="/static/uploads/meals/chicken-rice.jpg",
                diet_tags=["muscle_gain", "high_protein"],
                ingredients=["chicken", "rice", "vegetables"],
            ),
            "beef_quinoa": get_or_create_meal(
                db,
                category_id=categories["lunch"].id,
                name_en="Beef Quinoa Bowl",
                name_ar="وعاء لحم البقر والكينوا",
                price=55,
                calories=700,
                protein=50,
                carbs=65,
                fat=22,
                image_url="/static/uploads/meals/beef-quinoa.jpg",
                diet_tags=["muscle_gain"],
                ingredients=["beef", "quinoa", "vegetables"],
            ),
            "salmon": get_or_create_meal(
                db,
                category_id=categories["dinner"].id,
                name_en="Salmon Sweet Potato",
                name_ar="سلمون مع البطاطا الحلوة",
                price=60,
                calories=580,
                protein=42,
                carbs=45,
                fat=20,
                image_url="/static/uploads/meals/salmon.jpg",
                diet_tags=["healthy_lifestyle"],
                ingredients=["salmon", "sweet potato", "vegetables"],
                allergens=["fish"],
            ),
            "vegetable_pasta": get_or_create_meal(
                db,
                category_id=categories["dinner"].id,
                name_en="Vegetable Pasta",
                name_ar="مكرونة بالخضروات",
                price=35,
                calories=500,
                protein=18,
                carbs=75,
                fat=12,
                image_url="/static/uploads/meals/pasta.jpg",
                diet_tags=["maintenance"],
                ingredients=["pasta", "tomato", "vegetables"],
                allergens=["gluten"],
            ),
        }

        # ------------------------------------------------------------------
        # Subscription plans
        # ------------------------------------------------------------------
        plans = {
            "weight_loss": get_or_create_plan(
                db,
                name_en="Weight Loss Weekly Plan",
                name_ar="خطة أسبوعية لخسارة الوزن",
                plan_type=PlanType.WEEKLY,
                goal=PlanGoal.WEIGHT_LOSS,
                price=250,
                duration_days=7,
                meals_per_day=3,
                image_url="/static/uploads/plans/weight-loss.jpg",
            ),
            "muscle_gain": get_or_create_plan(
                db,
                name_en="Muscle Gain Monthly Plan",
                name_ar="خطة شهرية لزيادة العضلات",
                plan_type=PlanType.MONTHLY,
                goal=PlanGoal.MUSCLE_GAIN,
                price=1200,
                duration_days=30,
                meals_per_day=3,
                image_url="/static/uploads/plans/muscle-gain.jpg",
            ),
            "healthy": get_or_create_plan(
                db,
                name_en="Healthy Lifestyle Weekly Plan",
                name_ar="خطة أسبوعية لنمط حياة صحي",
                plan_type=PlanType.WEEKLY,
                goal=PlanGoal.HEALTHY_LIFESTYLE,
                price=300,
                duration_days=7,
                meals_per_day=3,
                image_url="/static/uploads/plans/healthy.jpg",
            ),
        }

        # Builds Monday–Sunday menu records for all three plans.
        build_weekly_menus(
            db,
            plans=plans,
            categories=categories,
            meals=meals,
        )

        # ------------------------------------------------------------------
        # Active + paid subscriptions, which automation can process
        # ------------------------------------------------------------------
        subscriptions = [
            get_or_create_active_subscription(
                db,
                user_id=customers[0].id,
                plan=plans["weight_loss"],
                notes="Mock active paid Weight Loss subscription",
            ),
            get_or_create_active_subscription(
                db,
                user_id=customers[1].id,
                plan=plans["muscle_gain"],
                notes="Mock active paid Muscle Gain subscription",
            ),
            get_or_create_active_subscription(
                db,
                user_id=customers[2].id,
                plan=plans["healthy"],
                notes="Mock active paid Healthy Lifestyle subscription",
            ),
        ]

        for customer in customers:
            create_notification_once(
                db,
                user_id=customer.id,
                title="Welcome to NutrioMeals",
                message=(
                    "Your mock account is active, paid and ready "
                    "for automatic meal-order generation."
                ),
            )

        # ------------------------------------------------------------------
        # Generate today's confirmed orders and tomorrow's scheduled orders
        # ------------------------------------------------------------------
        today = date.today()
        tomorrow = today + timedelta(days=1)

        generated_today = generate_orders_for_date(
            db=db,
            target_date=today,
        )

        # Safe when today's orders already existed as SCHEDULED.
        confirmed_today = confirm_scheduled_orders_for_date(
            db=db,
            target_date=today,
        )

        generated_tomorrow = generate_orders_for_date(
            db=db,
            target_date=tomorrow,
        )

        print("✅ Mock subscription-driven data seeded successfully")
        print("")
        print("Automation result:")
        print("  generated today:", generated_today)
        print("  confirmed today:", confirmed_today)
        print("  generated tomorrow:", generated_tomorrow)
        print("")
        print("Shared password for all mock users:")
        print(f"  {PASSWORD}")
        print("")
        print("Admin:")
        print("  nutriomeals0@gmail.com")
        print("")
        print("Super Admin:")
        print("  nutriomeals1@gmail.com")
        print("")
        print("Chef:")
        print("  chef@test.com")
        print("")
        print("Driver:")
        print("  driver@test.com")
        print("")
        print("Customers:")
        print("  customer1@test.com  -> Weight Loss")
        print("  customer2@test.com  -> Muscle Gain")
        print("  customer3@test.com  -> Healthy Lifestyle")
        print("")
        print("Created/updated subscription IDs:")
        print(" ", [subscription.id for subscription in subscriptions])

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()