from datetime import date, timedelta

from app.db.database import SessionLocal
from app.modules.orders.automation_service import (
    confirm_scheduled_orders_for_date,
    generate_orders_for_date,
)


def main():
    db = SessionLocal()

    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)

        confirmed = (
            confirm_scheduled_orders_for_date(
                db=db,
                target_date=today,
            )
        )

        generated = generate_orders_for_date(
            db=db,
            target_date=tomorrow,
        )

        print(
            {
                "confirmed_today": confirmed,
                "generated_tomorrow": generated,
            }
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()