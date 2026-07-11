from app.db.database import SessionLocal
from app.modules.rbac.models import Permission

PERMISSIONS = [
    # Dashboard
    ("dashboard.view", "View dashboard"),

    # RBAC
    ("rbac.manage", "Manage Roles & Permissions"),

    # Users
    ("users.view", "View users"),
    ("users.create", "Create users"),
    ("users.update", "Update users"),
    ("users.delete", "Delete users"),

    # Customers
    ("customers.view", "View customers"),
    ("customers.update", "Update customers"),
    ("customers.delete", "Delete customers"),

    # Meal Categories
    ("meal_categories.view", "View meal categories"),
    ("meal_categories.create", "Create meal category"),
    ("meal_categories.update", "Update meal category"),
    ("meal_categories.delete", "Delete meal category"),

    # Meals
    ("meals.view", "View meals"),
    ("meals.create", "Create meals"),
    ("meals.update", "Update meals"),
    ("meals.delete", "Delete meals"),

    # Meal Plans
    ("meal_plans.view", "View meal plans"),
    ("meal_plans.create", "Create meal plans"),
    ("meal_plans.update", "Update meal plans"),
    ("meal_plans.delete", "Delete meal plans"),

    # Nutrition
    ("nutrition.view", "View nutrition"),
    ("nutrition.update", "Update nutrition"),

    # Subscriptions
    ("subscriptions.view", "View subscriptions"),
    ("subscriptions.create", "Create subscriptions"),
    ("subscriptions.update", "Update subscriptions"),
    ("subscriptions.cancel", "Cancel subscriptions"),

    # Orders
    ("orders.view", "View orders"),
    ("orders.create", "Create orders"),
    ("orders.update", "Update orders"),
    ("orders.delete", "Delete orders"),

    # Payments
    ("payments.view", "View payments"),
    ("payments.refund", "Refund payments"),
    ("payments.export", "Export payment reports"),

    # Delivery
    ("deliveries.view", "View deliveries"),
    ("deliveries.assign", "Assign driver"),
    ("deliveries.update", "Update delivery"),
    ("deliveries.routes", "Manage delivery routes"),

    # Drivers
    ("drivers.view", "View drivers"),
    ("drivers.create", "Create driver"),
    ("drivers.update", "Update driver"),
    ("drivers.delete", "Delete driver"),

    # Promotions
    ("promotions.view", "View promotions"),
    ("promotions.create", "Create promotions"),
    ("promotions.update", "Update promotions"),
    ("promotions.delete", "Delete promotions"),

    # Discount Codes
    ("discounts.view", "View discounts"),
    ("discounts.create", "Create discounts"),
    ("discounts.update", "Update discounts"),
    ("discounts.delete", "Delete discounts"),

    # Referral Rewards
    ("referrals.view", "View referrals"),
    ("referrals.manage", "Manage referral rewards"),

    # Notifications
    ("notifications.view", "View notifications"),
    ("notifications.send_email", "Send Email"),
    ("notifications.send_sms", "Send SMS"),
    ("notifications.send_whatsapp", "Send WhatsApp"),

    # Reports
    ("reports.view", "View reports"),
    ("reports.export", "Export reports"),

    # Analytics
    ("analytics.view", "View analytics"),

    # Settings
    ("settings.view", "View settings"),
    ("settings.update", "Update settings"),
]


def seed_permissions() -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for name, description in PERMISSIONS:
            exists = db.query(Permission).filter(Permission.name == name).first()
            if exists:
                skipped += 1
                continue

            db.add(Permission(name=name, description=description))
            created += 1

        db.commit()
        print(f"Seeded permissions: {created} created, {skipped} skipped")
    except Exception as e:
        db.rollback()
        print(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_permissions()