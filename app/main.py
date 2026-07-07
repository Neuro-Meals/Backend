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

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

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

@app.get("/")
def root():
    return {"message": "Nutrio Meals API", "status": "Running"}
