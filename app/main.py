from fastapi import FastAPI

from app.core.config import settings
from app.db.database import Base, engine

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.users.rbac_router import router as rbac_router
from app.modules.users.profile_router import router as profile_router
from app.modules.meals.router import router as meal_categories_router
from app.modules.meals.meal_router import router as meals_router
from app.modules.plans.router import router as plans_router
from app.modules.subscriptions.router import router as subscriptions_router
from app.modules.orders.router import router as orders_router
from app.modules.deliveries.router import router as deliveries_router
from app.modules.notifications.router import router as notifications_router
from fastapi.middleware.cors import CORSMiddleware
from app.modules.meal_selections.router import router as meal_selections_router
from app.modules.reports.router import router as reports_router
from fastapi.staticfiles import StaticFiles
from app.modules.payments.router import router as payments_router
from app.modules.uploads.router import router as uploads_router
from app.modules.driver.router import router as driver_router
from app.modules.nutrition.router import router as nutrition_router
from app.modules.coupons.router import router as coupons_router
from app.modules.reviews.router import router as reviews_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.locations.router import router as locations_router
from app.modules.chatbot.router import router as chatbot_router
from app.modules.chef.router import router as chef_router
from app.common.handlers import register_exception_handlers
from app.modules.customer_drivers.router import router as customer_driver_router
from app.modules.chef.admin_router import (
    router as chef_admin_router,
)
from app.modules.meal_assignments.router import (
    router as meal_assignments_router,
)
# from app.modules.plan_menus.router import (
#     router as plan_menus_router,
# )
from app.modules.orders.automation_router import (
    router as order_automation_router,
)

from pathlib import Path

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
)
register_exception_handlers(app)

# Serve static files using absolute path so it works regardless of CWD
_static_dir = Path(__file__).resolve().parent.parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# API_PREFIX = "/api/v1"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rbac_router)
app.include_router(profile_router)
app.include_router(meal_categories_router)
app.include_router(meals_router)
app.include_router(plans_router)
app.include_router(subscriptions_router)
app.include_router(orders_router)
app.include_router(deliveries_router)
app.include_router(notifications_router)
app.include_router(meal_selections_router)
app.include_router(reports_router)
app.include_router(uploads_router)
app.include_router(payments_router)
app.include_router(driver_router)
app.include_router(nutrition_router)
app.include_router(coupons_router)
app.include_router(reviews_router)
app.include_router(dashboard_router)
app.include_router(locations_router)
app.include_router(chatbot_router)
app.include_router(chef_router)
app.include_router(chef_admin_router)
# app.include_router(plan_menus_router)
app.include_router(order_automation_router)
app.include_router(meal_assignments_router)
app.include_router(customer_driver_router)
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Nutrio Meals API", "status": "Running"}
