from sqlalchemy.exc import SQLAlchemyError

from app.db.database import SessionLocal
from app.modules.users.models import User
from app.modules.users.rbac_models import (
    Permission,
    Role,
    RolePermission,
    UserRoleLink,
)


ROLES = [
    ("customer", "Customer"),
    ("admin", "Administrator"),
    ("super_admin", "Super administrator"),
    ("nutrition_manager", "Nutrition manager"),
    ("delivery_manager", "Delivery manager"),
    ("driver", "Delivery driver"),
    ("finance_manager", "Finance manager"),
    ("chef", "chef"),
]


ROLE_PERMISSIONS = {
    # Super admin receives every permission in the database.
    "super_admin": ["*"],

    # Admin receives all permissions.
    # You can restrict this later through your RBAC frontend.
    "admin": ["*"],

    "customer": [
        "subscriptions.view",
        "subscriptions.create",
        "subscriptions.cancel",
        "orders.view",
        "orders.create",
        "notifications.view",
    ],

    "nutrition_manager": [
        "dashboard.view",
        "customers.view",
        "meal_categories.view",
        "meals.view",
        "meals.create",
        "meals.update",
        "meal_plans.view",
        "meal_plans.create",
        "meal_plans.update",
        "nutrition.view",
        "nutrition.update",
        "subscriptions.view",
        "orders.view",
        "notifications.view",
        "reports.view",
        "analytics.view",
    ],

    "delivery_manager": [
        "dashboard.view",
        "customers.view",
        "orders.view",
        "orders.update",
        "deliveries.view",
        "deliveries.assign",
        "deliveries.update",
        "deliveries.routes",
        "drivers.view",
        "drivers.create",
        "drivers.update",
        "drivers.delete",
        "notifications.view",
        "notifications.send_sms",
        "notifications.send_whatsapp",
        "reports.view",
        "analytics.view",
    ],

    "driver": [
        "dashboard.view",
        "orders.view",
        "deliveries.view",
        "deliveries.update",
        "notifications.view",
    ],

    "finance_manager": [
        "dashboard.view",
        "customers.view",
        "subscriptions.view",
        "subscriptions.update",
        "subscriptions.cancel",
        "orders.view",
        "payments.view",
        "payments.refund",
        "payments.export",
        "promotions.view",
        "promotions.create",
        "promotions.update",
        "discounts.view",
        "discounts.create",
        "discounts.update",
        "discounts.delete",
        "referrals.view",
        "referrals.manage",
        "reports.view",
        "reports.export",
        "analytics.view",
    ],
    
    "chef": [
        "dashboard.view",
        "dashboard",
        "orders.view",
        "orders.prepare",
        "orders.ready",
        "drivers.view",
        "deliveries.assign",
    ]
}


def normalize_role_name(value) -> str | None:
    """
    Convert UserRole.ADMIN, 'ADMIN', or 'admin' into 'admin'.
    """
    if value is None:
        return None

    if hasattr(value, "value"):
        value = value.value

    return str(value).strip().lower()


def create_roles(db) -> dict[str, Role]:
    role_map: dict[str, Role] = {}

    for name, description in ROLES:
        role = db.query(Role).filter(Role.name == name).first()

        if not role:
            role = Role(
                name=name,
                description=description,
            )
            db.add(role)
            db.flush()
            print(f"Created role: {name}")
        else:
            if role.description != description:
                role.description = description

            print(f"Role already exists: {name}")

        role_map[name] = role

    return role_map


def assign_permissions_to_roles(db, role_map: dict[str, Role]) -> None:
    all_permissions = db.query(Permission).order_by(Permission.id).all()

    if not all_permissions:
        raise RuntimeError(
            "No permissions found. Run: python -m app.db.seed_permissions"
        )

    permissions_by_code = {
        permission.code: permission
        for permission in all_permissions
    }

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = role_map.get(role_name)

        if not role:
            print(f"Skipped unknown role: {role_name}")
            continue

        if "*" in permission_codes:
            selected_permissions = all_permissions
        else:
            selected_permissions = []

            for code in permission_codes:
                permission = permissions_by_code.get(code)

                if not permission:
                    print(
                        f"Warning: permission '{code}' does not exist "
                        f"for role '{role_name}'"
                    )
                    continue

                selected_permissions.append(permission)

        added_count = 0

        for permission in selected_permissions:
            existing_link = (
                db.query(RolePermission)
                .filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permission.id,
                )
                .first()
            )

            if existing_link:
                continue

            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )
            added_count += 1

        print(
            f"Role '{role_name}': "
            f"{len(selected_permissions)} selected, "
            f"{added_count} newly assigned"
        )


def link_users_to_roles(db, role_map: dict[str, Role]) -> None:
    users = db.query(User).order_by(User.id).all()

    linked_count = 0

    for user in users:
        role_name = normalize_role_name(user.role)

        if not role_name:
            print(f"User {user.email} has no primary role")
            continue

        role = role_map.get(role_name)

        if not role:
            print(
                f"User {user.email} has unsupported role: {role_name}"
            )
            continue

        existing_link = (
            db.query(UserRoleLink)
            .filter(
                UserRoleLink.user_id == user.id,
                UserRoleLink.role_id == role.id,
            )
            .first()
        )

        if existing_link:
            print(
                f"User already linked: {user.email} -> {role_name}"
            )
            continue

        db.add(
            UserRoleLink(
                user_id=user.id,
                role_id=role.id,
            )
        )

        linked_count += 1
        print(f"Linked user: {user.email} -> {role_name}")

    print(f"New user-role links created: {linked_count}")


def seed_rbac() -> None:
    db = SessionLocal()

    try:
        print("Starting RBAC seed...")

        role_map = create_roles(db)
        assign_permissions_to_roles(db, role_map)
        link_users_to_roles(db, role_map)

        db.commit()

        print("RBAC seed completed successfully.")

    except SQLAlchemyError as exc:
        db.rollback()
        print(f"Database error while seeding RBAC: {exc}")
        raise

    except Exception as exc:
        db.rollback()
        print(f"Error while seeding RBAC: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_rbac()
