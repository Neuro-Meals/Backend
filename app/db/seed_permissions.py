from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.modules.users.rbac_models import Permission


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

    # Deliveries
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
    
    # Chef / Kitchen
    ("chef.dashboard", "View chef dashboard"),
    ("chef.orders.view", "View kitchen orders"),
    ("chef.orders.prepare", "Start order preparation"),
    ("chef.orders.ready", "Mark order ready for delivery"),
    ("chef.drivers.view", "View available drivers"),
    ("chef.deliveries.assign", "Assign drivers to ready orders"),
    
    
    # Chef administration
    ("chefs.view", "View chefs"),
    ("chefs.create", "Create chefs"),
    ("chefs.update", "Update chefs"),
    ("chefs.activate", "Activate chefs"),
    ("chefs.deactivate", "Deactivate chefs"),
    ("chefs.assign_role", "Assign chef role"),
    ("chefs.remove_role", "Remove chef role"),

# Chef kitchen operations
    ("chef.dashboard", "View chef dashboard"),
    ("chef.orders.view", "View kitchen orders"),
    ("chef.orders.prepare", "Start order preparation"),
    ("chef.orders.ready", "Mark order ready for delivery"),
    ("chef.drivers.view", "View available drivers"),
    ("chef.deliveries.assign", "Assign driver to ready order"),
]


def seed_permissions() -> None:
    db = SessionLocal()

    try:
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for code, description in PERMISSIONS:
            permission = (
                db.query(Permission)
                .filter(Permission.code == code)
                .first()
            )

            if permission:
                if permission.description != description:
                    permission.description = description
                    updated_count += 1
                else:
                    skipped_count += 1

                continue

            permission = Permission(
                code=code,
                description=description,
            )

            db.add(permission)
            created_count += 1

        db.commit()

        print("Permission seeding completed")
        print(f"Created: {created_count}")
        print(f"Updated: {updated_count}")
        print(f"Already existed: {skipped_count}")

    except SQLAlchemyError as exc:
        db.rollback()
        print(f"Database error while seeding permissions: {exc}")
        raise

    except Exception as exc:
        db.rollback()
        print(f"Unexpected error while seeding permissions: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_permissions()