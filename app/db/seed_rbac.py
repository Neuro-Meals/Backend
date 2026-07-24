from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Import all SQLAlchemy model modules before mapper configuration.
import app.db.models  # noqa: F401

from app.db.database import SessionLocal
from app.modules.users.models import User
from app.modules.users.rbac_models import (
    Permission,
    Role,
    RolePermission,
    UserRoleLink,
)


ROLES: list[tuple[str, str]] = [
    ("customer", "Customer"),
    ("admin", "Administrator"),
    ("super_admin", "Super administrator"),
    ("nutrition_manager", "Nutrition manager"),
    ("delivery_manager", "Delivery manager"),
    ("driver", "Delivery driver"),
    ("finance_manager", "Finance manager"),
    ("chef", "Chef"),
]


ROLE_PERMISSIONS: dict[str, list[str]] = {
    # Super admin receives every permission in the database.
    "super_admin": ["*"],

    # Admin currently receives every permission.
    # Permissions can later be customized through the RBAC frontend.
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

    # All codes below match the codes in seed_permissions.py.
    "chef": [
        "chef.dashboard",
        "chef.orders.view",
        "chef.orders.prepare",
        "chef.orders.ready",
        "chef.drivers.view",
        "chef.deliveries.assign",
        "chef.orders.today",
        "chef.orders.tomorrow",
        "chef.meals.summary",
        "chef.allergies.summary",
        "chef.orders.ready_for_delivery",
        "notifications.view",
    ],
}


def normalize_role_name(value: Any) -> str | None:
    """
    Convert values such as UserRole.ADMIN, "ADMIN", or "admin"
    into the normalized string "admin".
    """
    if value is None:
        return None

    if hasattr(value, "value"):
        value = value.value

    normalized = str(value).strip().lower()
    return normalized or None


def validate_role_configuration() -> None:
    """
    Validate the local role configuration before accessing the database.
    """
    configured_role_names = [name for name, _ in ROLES]

    duplicate_roles = {
        role_name
        for role_name in configured_role_names
        if configured_role_names.count(role_name) > 1
    }

    if duplicate_roles:
        raise RuntimeError(
            "Duplicate role definitions found: "
            f"{sorted(duplicate_roles)}"
        )

    unknown_role_mappings = (
        set(ROLE_PERMISSIONS) - set(configured_role_names)
    )

    if unknown_role_mappings:
        raise RuntimeError(
            "Permission mappings exist for unknown roles: "
            f"{sorted(unknown_role_mappings)}"
        )

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        duplicates = {
            code
            for code in permission_codes
            if permission_codes.count(code) > 1
        }

        if duplicates:
            raise RuntimeError(
                f"Role '{role_name}' contains duplicate permission codes: "
                f"{sorted(duplicates)}"
            )


def create_roles(db: Session) -> dict[str, Role]:
    """
    Create missing roles and update changed role descriptions.
    """
    role_map: dict[str, Role] = {}

    for name, description in ROLES:
        role = (
            db.query(Role)
            .filter(Role.name == name)
            .first()
        )

        if role is None:
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
                print(f"Updated role description: {name}")
            else:
                print(f"Role already exists: {name}")

        role_map[name] = role

    return role_map


def get_permissions_by_code(
    db: Session,
) -> tuple[list[Permission], dict[str, Permission]]:
    """
    Load all permissions and create a lookup dictionary by code.
    """
    all_permissions = (
        db.query(Permission)
        .order_by(Permission.id)
        .all()
    )

    if not all_permissions:
        raise RuntimeError(
            "No permissions found. Run this command first:\n"
            "python -m app.db.seed_permissions"
        )

    permissions_by_code = {
        permission.code: permission
        for permission in all_permissions
    }

    return all_permissions, permissions_by_code


def assign_permissions_to_roles(
    db: Session,
    role_map: dict[str, Role],
) -> None:
    """
    Assign configured permissions to roles without creating duplicates.

    This function adds missing role-permission links. It does not remove
    existing links, so permissions assigned through the frontend remain
    untouched.
    """
    all_permissions, permissions_by_code = get_permissions_by_code(db)

    missing_permission_codes: list[tuple[str, str]] = []

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = role_map.get(role_name)

        if role is None:
            print(f"Skipped unknown role: {role_name}")
            continue

        if "*" in permission_codes:
            selected_permissions = all_permissions
        else:
            selected_permissions = []

            for code in permission_codes:
                permission = permissions_by_code.get(code)

                if permission is None:
                    missing_permission_codes.append(
                        (role_name, code)
                    )
                    continue

                selected_permissions.append(permission)

        existing_permission_ids = {
            permission_id
            for (permission_id,) in (
                db.query(RolePermission.permission_id)
                .filter(RolePermission.role_id == role.id)
                .all()
            )
        }

        added_count = 0
        already_assigned_count = 0

        for permission in selected_permissions:
            if permission.id in existing_permission_ids:
                already_assigned_count += 1
                continue

            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                )
            )

            existing_permission_ids.add(permission.id)
            added_count += 1

        print(
            f"Role '{role_name}': "
            f"{len(selected_permissions)} selected, "
            f"{added_count} newly assigned, "
            f"{already_assigned_count} already assigned"
        )

    if missing_permission_codes:
        print("\nMissing permission codes:")

        for role_name, code in missing_permission_codes:
            print(
                f" - Role '{role_name}': permission '{code}' "
                "does not exist"
            )

        raise RuntimeError(
            "Some ROLE_PERMISSIONS codes do not exist in the "
            "permissions table. Fix the codes or update "
            "seed_permissions.py."
        )


def link_users_to_roles(
    db: Session,
    role_map: dict[str, Role],
) -> None:
    """
    Create a UserRoleLink based on each user's primary User.role value.
    """
    users = (
        db.query(User)
        .order_by(User.id)
        .all()
    )

    linked_count = 0
    already_linked_count = 0
    skipped_count = 0

    for user in users:
        role_name = normalize_role_name(user.role)

        if role_name is None:
            print(f"User {user.email} has no primary role")
            skipped_count += 1
            continue

        role = role_map.get(role_name)

        if role is None:
            print(
                f"User {user.email} has unsupported role: "
                f"{role_name}"
            )
            skipped_count += 1
            continue

        existing_link = (
            db.query(UserRoleLink)
            .filter(
                UserRoleLink.user_id == user.id,
                UserRoleLink.role_id == role.id,
            )
            .first()
        )

        if existing_link is not None:
            already_linked_count += 1
            continue

        db.add(
            UserRoleLink(
                user_id=user.id,
                role_id=role.id,
            )
        )

        linked_count += 1
        print(f"Linked user: {user.email} -> {role_name}")

    print(
        "User-role linking: "
        f"{linked_count} created, "
        f"{already_linked_count} already existed, "
        f"{skipped_count} skipped"
    )


def seed_rbac() -> None:
    """
    Seed roles, assign permissions, and link users to their primary roles.
    """
    validate_role_configuration()

    db = SessionLocal()

    try:
        print("Starting RBAC seed...")

        role_map = create_roles(db)

        assign_permissions_to_roles(
            db=db,
            role_map=role_map,
        )

        link_users_to_roles(
            db=db,
            role_map=role_map,
        )

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