from datetime import datetime, timedelta

from app.db.database import Base, engine, SessionLocal
from app.core.security import hash_password

from app.modules.users.models import User, UserRole, Gender, FitnessGoal
from app.modules.meals.models import MealCategory, Meal
from app.modules.plans.models import MealPlan, MealPlanItem, PlanType, PlanGoal
from app.modules.subscriptions.models import Subscription, SubscriptionStatus, PaymentStatus
from app.modules.orders.models import Order, OrderStatus
from app.modules.deliveries.models import Delivery, DeliveryStatus
from app.modules.notifications.models import Notification


PASSWORD = "Amro&258"


def get_or_create_user(db, email, phone, role):
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        first_name=role.value.replace("_", " ").title(),
        last_name="Test",
        email=email,
        phone=phone,
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_active=True,
        is_verified=True,
        gender=Gender.MALE,
        age=25,
        height_cm=175,
        weight_kg=70,
        fitness_goal=FitnessGoal.MAINTENANCE,
        dietary_preference="balanced diet",
        allergies=[],
        created_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_category(db, name_en, name_ar, image_url):
    category = db.query(MealCategory).filter(MealCategory.name_en == name_en).first()
    if category:
        return category

    category = MealCategory(
        name_en=name_en,
        name_ar=name_ar,
        description=f"{name_en} meals",
        image_url=image_url,
        is_active=True,
    )

    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def get_or_create_meal(db, category_id, name_en, price, calories, protein, carbs, fat, image_url, diet_tags):
    meal = db.query(Meal).filter(Meal.name_en == name_en).first()
    if meal:
        return meal

    meal = Meal(
        category_id=category_id,
        name_en=name_en,
        name_ar=None,
        description_en=f"Healthy {name_en}",
        description_ar=None,
        calories=calories,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        fiber_g=5,
        sugar_g=3,
        sodium_mg=250,
        price=price,
        image_url=image_url,
        ingredients=["rice", "vegetables", "protein"],
        allergens=[],
        diet_tags=diet_tags,
        is_available=True,
    )

    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal


def get_or_create_plan(db, name_en, plan_type, goal, price, duration_days, meals_per_day, image_url):
    plan = db.query(MealPlan).filter(MealPlan.name_en == name_en).first()
    if plan:
        return plan

    plan = MealPlan(
        name_en=name_en,
        name_ar=None,
        description_en=f"{name_en} subscription plan",
        description_ar=None,
        plan_type=plan_type,
        goal=goal,
        price=price,
        duration_days=duration_days,
        meals_per_day=meals_per_day,
        total_meals=duration_days * meals_per_day,
        image_url=image_url,
        is_active=True,
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def add_plan_item(db, plan_id, meal_id, day_number, meal_time):
    exists = db.query(MealPlanItem).filter(
        MealPlanItem.plan_id == plan_id,
        MealPlanItem.meal_id == meal_id,
        MealPlanItem.day_number == day_number,
        MealPlanItem.meal_time == meal_time,
    ).first()

    if exists:
        return exists

    item = MealPlanItem(
        plan_id=plan_id,
        meal_id=meal_id,
        day_number=day_number,
        meal_time=meal_time,
        is_active=True,
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        admin = get_or_create_user(db, "nutriomeals0@gmail.com", "+966000000000", UserRole.ADMIN)
        super_admin = get_or_create_user(db, "nutriomeals1@gmail.com", "+966000000001", UserRole.SUPER_ADMIN)
        customer = get_or_create_user(db, "customer@test.com", "+966000000002", UserRole.CUSTOMER)
        driver = get_or_create_user(db, "driver@test.com", "+966000000003", UserRole.DRIVER)

        breakfast = get_or_create_category(db, "Breakfast", "فطور", "/static/uploads/categories/breakfast.jpg")
        lunch = get_or_create_category(db, "Lunch", "غداء", "/static/uploads/categories/lunch.jpg")
        dinner = get_or_create_category(db, "Dinner", "عشاء", "/static/uploads/categories/dinner.jpg")
        snacks = get_or_create_category(db, "Snacks", "وجبات خفيفة", "/static/uploads/categories/snacks.jpg")

        meals = [
            get_or_create_meal(db, breakfast.id, "Oats Banana Bowl", 25, 350, 15, 55, 8, "/static/uploads/meals/oats.jpg", ["weight_loss", "healthy_lifestyle"]),
            get_or_create_meal(db, breakfast.id, "Egg Avocado Toast", 30, 420, 22, 35, 18, "/static/uploads/meals/egg-toast.jpg", ["high_protein"]),
            get_or_create_meal(db, lunch.id, "Grilled Chicken Rice", 45, 620, 48, 60, 15, "/static/uploads/meals/chicken-rice.jpg", ["muscle_gain", "high_protein"]),
            get_or_create_meal(db, lunch.id, "Beef Quinoa Bowl", 55, 700, 50, 65, 22, "/static/uploads/meals/beef-quinoa.jpg", ["muscle_gain"]),
            get_or_create_meal(db, dinner.id, "Salmon Sweet Potato", 60, 580, 42, 45, 20, "/static/uploads/meals/salmon.jpg", ["healthy_lifestyle"]),
            get_or_create_meal(db, dinner.id, "Vegetable Pasta", 35, 500, 18, 75, 12, "/static/uploads/meals/pasta.jpg", ["maintenance"]),
            get_or_create_meal(db, snacks.id, "Protein Smoothie", 20, 280, 25, 25, 6, "/static/uploads/meals/smoothie.jpg", ["high_protein"]),
            get_or_create_meal(db, snacks.id, "Greek Yogurt Bowl", 18, 240, 20, 20, 5, "/static/uploads/meals/yogurt.jpg", ["weight_loss"]),
        ]

        weight_loss_plan = get_or_create_plan(
            db,
            "Weight Loss Weekly Plan",
            PlanType.WEEKLY,
            PlanGoal.WEIGHT_LOSS,
            250,
            7,
            3,
            "/static/uploads/plans/weight-loss.jpg",
        )

        muscle_plan = get_or_create_plan(
            db,
            "Muscle Gain Monthly Plan",
            PlanType.MONTHLY,
            PlanGoal.MUSCLE_GAIN,
            1200,
            30,
            3,
            "/static/uploads/plans/muscle-gain.jpg",
        )

        healthy_plan = get_or_create_plan(
            db,
            "Healthy Lifestyle Weekly Plan",
            PlanType.WEEKLY,
            PlanGoal.HEALTHY_LIFESTYLE,
            300,
            7,
            3,
            "/static/uploads/plans/healthy.jpg",
        )

        for day in range(1, 8):
            add_plan_item(db, weight_loss_plan.id, meals[0].id, day, "breakfast")
            add_plan_item(db, weight_loss_plan.id, meals[2].id, day, "lunch")
            add_plan_item(db, weight_loss_plan.id, meals[4].id, day, "dinner")

            add_plan_item(db, healthy_plan.id, meals[1].id, day, "breakfast")
            add_plan_item(db, healthy_plan.id, meals[5].id, day, "lunch")
            add_plan_item(db, healthy_plan.id, meals[7].id, day, "snack")

        for day in range(1, 31):
            add_plan_item(db, muscle_plan.id, meals[1].id, day, "breakfast")
            add_plan_item(db, muscle_plan.id, meals[3].id, day, "lunch")
            add_plan_item(db, muscle_plan.id, meals[6].id, day, "snack")

        subscription = db.query(Subscription).filter(
            Subscription.user_id == customer.id,
            Subscription.plan_id == muscle_plan.id,
        ).first()

        if not subscription:
            subscription = Subscription(
                user_id=customer.id,
                plan_id=muscle_plan.id,
                status=SubscriptionStatus.PENDING_PAYMENT,
                payment_status=PaymentStatus.UNPAID,
                amount=muscle_plan.price,
                notes="Demo pending subscription",
            )
            db.add(subscription)
            db.commit()
            db.refresh(subscription)

        order = db.query(Order).filter(Order.subscription_id == subscription.id).first()

        if not order:
            order = Order(
                user_id=customer.id,
                subscription_id=subscription.id,
                plan_id=muscle_plan.id,
                order_number=f"ORD-DEMO-{subscription.id}",
                status=OrderStatus.PENDING,
                total_amount=subscription.amount,
                delivery_date=datetime.utcnow() + timedelta(days=1),
                delivery_address="Riyadh, King Fahd Road",
                delivery_notes="Demo order",
                items=[
                    {
                        "plan_id": muscle_plan.id,
                        "plan_name": muscle_plan.name_en,
                        "total_meals": muscle_plan.total_meals,
                    }
                ],
            )
            db.add(order)
            db.commit()
            db.refresh(order)

        delivery = db.query(Delivery).filter(Delivery.order_id == order.id).first()

        if not delivery:
            delivery = Delivery(
                order_id=order.id,
                user_id=customer.id,
                driver_id=driver.id,
                status=DeliveryStatus.ASSIGNED,
                delivery_address=order.delivery_address,
                delivery_notes="Demo delivery",
                scheduled_at=datetime.utcnow() + timedelta(days=1),
            )
            db.add(delivery)
            db.commit()

        exists_notification = db.query(Notification).filter(
            Notification.user_id == customer.id,
            Notification.title == "Welcome to NutrioMeals",
        ).first()

        if not exists_notification:
            notification = Notification(
                user_id=customer.id,
                title="Welcome to NutrioMeals",
                message="Your demo account is ready for testing.",
                notification_type="general",
                channel="in_app",
                is_read=False,
            )
            db.add(notification)
            db.commit()

        print("✅ Mock data seeded successfully")
        print("")
        print("Admin login:")
        print("  email: nutriomeals0@gmail.com")
        print("  password: Amro&258")
        print("")
        print("Super Admin login:")
        print("  email: nutriomeals1@gmail.com")
        print("  password: Amro&258")
        print("")
        print("Customer login:")
        print("  email: customer@test.com")
        print("  password: Amro&258")
        print("")
        print("Driver login:")
        print("  email: driver@test.com")
        print("  password: Amro&258")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
