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

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
)

# API_PREFIX = "/api/v1"

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rbac_router)
app.include_router(profile_router)
app.include_router(meal_categories_router)
app.include_router(meals_router)
app.include_router(plans_router)

@app.get("/")
def root():
    return {"message": "Nutrio Meals API", "status": "Running"}
