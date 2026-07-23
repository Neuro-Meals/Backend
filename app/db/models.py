"""
SQLAlchemy model registry.

Importing this module registers all models with Base.metadata.
Do not import this module from app.db.database.
"""

from app.modules.customer_drivers.models import CustomerDriverAssignment
from app.modules.deliveries.models import Delivery
from app.modules.meal_assignments.models import MealAssignment
from app.modules.meals.models import Meal, MealCategory
from app.modules.orders.models import Order
from app.modules.payments.models import Payment
from app.modules.plans.models import MealPlan
from app.modules.subscriptions.models import Subscription
from app.modules.users.models import (
    User,
    UserCategoryDeliveryPreference,
)

__all__ = [
    "CustomerDriverAssignment",
    "Delivery",
    "MealAssignment",
    "Meal",
    "MealCategory",
    "Order",
    "Payment",
    "MealPlan",
    "Subscription",
    "User",
    "UserCategoryDeliveryPreference",
]